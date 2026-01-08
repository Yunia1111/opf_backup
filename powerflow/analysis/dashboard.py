"""
Visualizer - Generates interactive folium maps of the power grid.
MERGED VERSION: High-detail layers + Voltage Heatmap + Directional Arrows + Robust Coord Parsing.
FIXED: Hover Tooltips for Lines with Detailed Data.
"""
import streamlit as st
import pandas as pd
import sys
import os
import time
import copy
import json
import altair as alt
import glob

# ==========================================
# 1. 环境与路径设置
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path: sys.path.insert(0, project_root)

from powerflow.analysis import config, grid_building, opf, visualization, report_export
# [NEW] Explicitly import DEFAULT_GEN_COSTS to use as master list
from powerflow.analysis.scenarios import SCENARIOS as PRESET_SCENARIOS, DEFAULT_GEN_COSTS

# ==========================================
# 2. 页面配置与 CSS
# ==========================================
st.set_page_config(page_title="German Grid OPF Studio", layout="wide", page_icon="⚡")
st.markdown("""<style>
    div[data-testid="stVerticalBlock"] > div { margin-bottom: -0.5rem; }
    div.stNumberInput, div.stSlider { padding-bottom: 0rem; }
    .streamlit-expanderContent div { margin-bottom: 0rem !important; }
    [data-testid="stDataFrame"] { width: 100%; }
    .caption-text { font-size: 0.85em; color: #555; margin-top: -10px; margin-bottom: 10px; }
    .debug-text { font-size: 0.75em; color: #d63031; font-family: monospace; }
</style>""", unsafe_allow_html=True)

st.title("⚡ German Transmission Grid OPF Studio")

# ==========================================
# 3. 辅助函数：键名标准化
# ==========================================
def normalize_key(key):
    """
    Robust normalization:
    1. Check string type
    2. Lowercase
    3. Strip spaces
    4. Replace underscores with spaces (unify 'wind_onshore' and 'wind onshore')
    """
    if not isinstance(key, str): return "other"
    return key.lower().strip().replace('_', ' ').replace('-', ' ')

# ==========================================
# 4. 初始化状态与电网加载
# ==========================================
if 'scenario_storage' not in st.session_state:
    st.session_state['scenario_storage'] = copy.deepcopy(PRESET_SCENARIOS)

if 'selected_scenario_name' not in st.session_state:
    st.session_state['selected_scenario_name'] = 'average_of_2025'

# [NEW] Clear Cache Functionality
if st.sidebar.button("🔄 Force Rebuild Network Cache"):
    cache_path = os.path.join(config.OUTPUT_DIR, config.NETWORK_CACHE_FILE)
    if os.path.exists(cache_path):
        os.remove(cache_path)
        st.cache_resource.clear()
        st.success(f"Deleted {cache_path}. Reloading...")
        time.sleep(1)
        st.rerun()
    else:
        st.warning("No cache file found to delete. Just reloading...")
        st.cache_resource.clear()
        st.rerun()

@st.cache_resource
def load_base_network_cached():
    modeler = grid_building.GridModeler()
    # forcing cache rebuild if it was deleted just now
    base_net, ext_grids = modeler.create_base_network()
    
    neighbor_countries = set()
    for eg in ext_grids:
        if eg.get('type') != 'main_slack' and 'country' in eg:
            neighbor_countries.add(eg['country'])
    
    # [UPDATED] Pre-calculate installed capacity per type (Robust Keys)
    installed_cap = {}
    
    # Debug list to see what we actually found
    found_types_raw = set()

    for net_gen in [base_net.gen, base_net.sgen, base_net.storage]:
        # Skip empty tables
        if net_gen.empty: continue

        has_max_p = 'max_p_mw' in net_gen.columns
        has_type = 'type' in net_gen.columns
        has_name = 'name' in net_gen.columns # Fallback if type missing
        
        for _, row in net_gen.iterrows():
            # 1. Identify Type
            raw_type = "unknown"
            if has_type and pd.notna(row['type']):
                raw_type = str(row['type'])
            elif has_name:
                # Fallback: try to guess from name if type is missing
                raw_type = str(row['name']).split('_')[0]
            
            found_types_raw.add(raw_type)

            # 2. Normalize
            t = normalize_key(raw_type)
            
            if 'border' in t or 'ext' in t: continue
            
            # 3. Identify Capacity
            cap = 0.0
            if has_max_p and pd.notna(row.get('max_p_mw')):
                cap = row['max_p_mw']
            else:
                cap = row.get('p_mw', row.get('sn_mva', 0))
                
            installed_cap[t] = installed_cap.get(t, 0) + cap
            
    return base_net, ext_grids, sorted(list(neighbor_countries)), installed_cap, list(found_types_raw)

try:
    base_net, external_grids, neighbor_list, installed_capacity_map, debug_found_types = load_base_network_cached()
except Exception as e:
    st.error(f"Failed to load grid: {e}")
    st.info("💡 Tip: Click 'Force Rebuild Network Cache' in the sidebar.")
    st.stop()

# ==========================================
# 5. 侧边栏：参数配置
# ==========================================
st.sidebar.header("🎛️ Scenario Configuration")

# --- Debug Expander (To diagnose your issue) ---
with st.sidebar.expander("🛠️ Debug: Data Inspection", expanded=False):
    st.write("keys in `installed_capacity_map` (Normalized):")
    st.json(installed_capacity_map)
    st.write("Raw types found in `net.gen/sgen`:")
    st.write(debug_found_types)
    st.info("If the list above is empty or weird, your cache is stale. Click 'Force Rebuild' above.")

# --- A. 场景选择 ---
available_scenarios = list(st.session_state['scenario_storage'].keys())
idx = available_scenarios.index('average_of_2025') if 'average_of_2025' in available_scenarios else 0

selected_scen_key = st.sidebar.selectbox(
    "Select Scenario", options=available_scenarios, index=idx,
    format_func=lambda x: st.session_state['scenario_storage'][x]['name']
)

current_scen_data = st.session_state['scenario_storage'][selected_scen_key]
defaults_cf = current_scen_data.get('capacity_factors', {})
default_load_scale = current_scen_data.get('load_scale', 1.0)
defaults_gen_costs = current_scen_data.get('generation_costs', config.GENERATION_COSTS)
defaults_import_costs = current_scen_data.get('import_costs', config.IMPORT_COST_PARAMS)

# --- B. 负荷设置 ---
st.sidebar.subheader("1. Demand Settings")
load_scale = st.sidebar.number_input("Global Load Scaling Factor", 0.5, 2.5, float(default_load_scale), 0.05)

# --- C. 发电出力系数 (CF) ---
st.sidebar.subheader("2. Generation Capacity Factors (CF)")

with st.sidebar.expander("Show/Hide Generators", expanded=True):
    # Use DEFAULT_GEN_COSTS as master list
    master_gen_types = [k for k in DEFAULT_GEN_COSTS.keys() if k != 'default']
    
    user_cfs = {}
    for gen_type in master_gen_types:
        default_val = float(defaults_cf.get(gen_type, 0.0))
        
        # [ROBUST LOOKUP STRATEGY]
        # 1. Try Normalized Match (ignore case, ignore underscores vs spaces)
        lookup_key = normalize_key(gen_type)
        cap = installed_capacity_map.get(lookup_key, 0)
        
        # 2. Fallback: Try Exact Raw Match if normalization failed 
        # (Only happens if normalization logic is buggy, but safety first)
        if cap == 0:
             cap = installed_capacity_map.get(gen_type, 0)

        # Label
        label_base = gen_type.replace('_', ' ').title()
        
        # Slider
        val = st.slider(f"{label_base}", 0.0, 1.0, default_val, 0.01, key=f"sl_{gen_type}")
        user_cfs[gen_type] = val
        
        # Feedback
        current_mw = val * cap
        if cap > 0:
            st.markdown(f"<div class='caption-text'>⚡ <b>{current_mw:,.0f} MW</b> / {cap:,.0f} MW (Installed)</div>", unsafe_allow_html=True)
        else:
            # Show the key we tried to find to help you debug
            st.markdown(f"<div class='debug-text'>⚠️ No Cap (Looked for: '{lookup_key}')</div>", unsafe_allow_html=True)

# --- D. 市场价格设置 ---
st.sidebar.subheader("3. Market Prices / Costs (€/MWh)")

with st.sidebar.expander("🏭 Domestic Generation Costs", expanded=False):
    user_gen_costs = {}
    for g_key in master_gen_types:
        default_global_cost = config.GENERATION_COSTS.get(g_key, 50)
        scen_cost = defaults_gen_costs.get(g_key, default_global_cost)
        label = g_key.replace('_', ' ').title()
        user_gen_costs[g_key] = st.number_input(f"{label}", value=float(scen_cost), step=1.0, key=f"cost_{g_key}")

# 邻国进口价格
with st.sidebar.expander("🌍 Neighboring Import Prices", expanded=False):
    user_border_costs = {}
    for country in neighbor_list:
        scen_params = defaults_import_costs.get(country, config.IMPORT_COST_PARAMS.get(country, {'c1': 50.0, 'c2': 0.02}))
        if country not in defaults_import_costs and 'default' in defaults_import_costs:
            scen_params = defaults_import_costs['default']
        st.markdown(f"**{country}**")
        c1_col, c2_col = st.columns(2)
        with c1_col:
            val_c1 = st.number_input(f"c1 (Price)", value=float(scen_params.get('c1', 50.0)), step=1.0, key=f"c1_{country}")
        with c2_col:
            val_c2 = st.number_input(f"c2 (Quad)", value=float(scen_params.get('c2', 0.0)), step=0.001, format="%.3f", key=f"c2_{country}")
        user_border_costs[country] = {'c1': val_c1, 'c2': val_c2}

# --- E. 保存新场景 ---
st.sidebar.markdown("---")
new_scen_name = st.sidebar.text_input("New Scenario Name", placeholder="e.g. High Cost Winter")
if st.sidebar.button("Save Configuration"):
    if new_scen_name:
        safe_id = new_scen_name.lower().replace(" ", "_")
        new_entry = {
            'name': new_scen_name, 
            'description': f"Custom UI {time.strftime('%H:%M')}",
            'capacity_factors': user_cfs, 
            'load_scale': load_scale,
            'generation_costs': user_gen_costs, 
            'import_costs': user_border_costs
        }
        st.session_state['scenario_storage'][safe_id] = new_entry
        st.success(f"Saved '{new_scen_name}'!")
        time.sleep(1)
        st.rerun()

# ==========================================
# 6. 主界面逻辑
# ==========================================
def show_results(kpi_data, map_html_path, folder_name):
    st.success(f"✅ Results Loaded for: **{kpi_data['scenario'].upper()}**")
    
    st.divider()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Load", f"{kpi_data['total_load_mw']/1000:.2f} GW")
    k2.metric("Generation", f"{kpi_data['total_gen_mw']/1000:.2f} GW")
    k3.metric("Cost", f"{kpi_data['total_cost_eur']:,.0f} €/h")
    net_imp = kpi_data['total_load_mw'] - kpi_data['total_gen_mw']
    k4.metric("Net Import", f"{net_imp/1000:.2f} GW")

    st.subheader("🗺️ Network Map")
    if os.path.exists(map_html_path):
        with open(map_html_path, 'r', encoding='utf-8') as f: 
            st.components.v1.html(f.read(), height=700)
    else:
        st.warning(f"⚠️ Map file not found at: {map_html_path}")

    st.subheader("📊 Generation Analysis")
    c_bar, c_pie = st.columns([2, 1])
    
    mix = kpi_data['gen_by_type']
    if mix:
        df_mix = pd.DataFrame(list(mix.items()), columns=['Type', 'MW'])
        df_mix = df_mix[df_mix['MW'] > 1.0] 
        total_mw = df_mix['MW'].sum()
        df_mix['Percent'] = df_mix['MW'] / total_mw if total_mw > 0 else 0.0
        
        color_domain = []
        color_range = []
        for k, v in config.GENERATOR_TYPE_COLORS.items():
            color_domain.append(k)
            color_range.append(v)

        with c_bar:
            st.markdown("##### Generation Mix (Domestic)")
            bar_chart = alt.Chart(df_mix).mark_bar().encode(
                x=alt.X('Type', axis=alt.Axis(labelAngle=-45, title="Generation Type")), 
                y=alt.Y('MW'),
                color=alt.Color('Type', scale=alt.Scale(domain=color_domain, range=color_range), legend=None),
                tooltip=['Type', 'MW', alt.Tooltip('Percent', format='.1%')]
            ).properties(height=350)
            st.altair_chart(bar_chart, use_container_width=True)

        with c_pie:
            st.markdown("##### Share")
            base = alt.Chart(df_mix).encode(theta=alt.Theta("MW", stack=True), order=alt.Order("MW", sort="descending"))
            pie = base.mark_arc(outerRadius=105).encode(
                color=alt.Color("Type", scale=alt.Scale(domain=color_domain, range=color_range), legend=None),
                tooltip=['Type', 'MW', alt.Tooltip('Percent', format='.1%')]
            )
            text = base.mark_text(radius=135).encode(
                text=alt.Text("Percent", format=".1%"),
                color=alt.value("black"),
                opacity=alt.condition(alt.datum.Percent > 0.04, alt.value(1), alt.value(0))
            )
            st.altair_chart((pie + text).properties(height=350), use_container_width=True)

    st.subheader("🌍 Cross-Border & Balancing Details")
    border_csv = os.path.join(config.OUTPUT_DIR, folder_name, 'import_export_results.csv')
    
    if os.path.exists(border_csv):
        try:
            df_border = pd.read_csv(border_csv)
            df_border['name'] = df_border['name'].astype(str)
            
            def extract_category(name):
                if "Slack" in name or "ExtGrid" in name: return "⚡ Balancing (Slack)"
                for country in neighbor_list:
                    if country in name: return country
                return "Other"

            df_border['Category'] = df_border['name'].apply(extract_category)
            group_sum = df_border.groupby('Category')['p_mw'].sum().reset_index()
            group_sum.rename(columns={'p_mw': 'Net_MW'}, inplace=True)
            df_merged = df_border.merge(group_sum, on='Category')
            df_merged['is_slack'] = df_merged['Category'].apply(lambda x: 0 if "Balancing" in x else 1)
            df_merged['abs_net'] = df_merged['Net_MW'].abs()
            df_merged.sort_values(by=['is_slack', 'abs_net', 'p_mw'], ascending=[True, False, False], inplace=True)
            
            final_data = []
            for cat in df_merged['Category'].unique():
                subset = df_merged[df_merged['Category'] == cat]
                net = subset['Net_MW'].iloc[0]
                d_net = "IMPORT" if net > 0.001 else ("EXPORT" if net < -0.001 else "NEUTRAL")
                final_data.append({'Region': cat, 'Connection': f"📊 TOTAL ({d_net})", 'Flow (MW)': abs(net), 'Status': d_net})
                
                name_counter = {}
                for _, row in subset.iterrows():
                    bn = row['name']
                    if bn in name_counter: name_counter[bn] += 1; disp = f"{bn} ({name_counter[bn]})"
                    else: name_counter[bn] = 1; disp = bn
                    d_row = "IMPORT" if row['p_mw'] > 0.001 else ("EXPORT" if row['p_mw'] < -0.001 else "NEUTRAL")
                    final_data.append({'Region': cat, 'Connection': f"  └─ {disp}", 'Flow (MW)': abs(row['p_mw']), 'Status': d_row})
            
            df_disp = pd.DataFrame(final_data)
            if df_disp.duplicated(subset=['Region', 'Connection']).any():
                df_disp['Connection'] = df_disp['Connection'] + " #" + df_disp.index.astype(str)
            df_disp.set_index(['Region', 'Connection'], inplace=True)
            
            def style_row(row):
                col = "#d4efdf" if row['Status'] == "IMPORT" else "#d6eaf8"
                if "TOTAL" in row.name[1]: return [f'background-color: {col}; font-weight: bold'] * len(row)
                return [''] * len(row)

            st.dataframe(df_disp.style.apply(style_row, axis=1).format({'Flow (MW)': '{:,.1f}'}), use_container_width=True)
        except Exception as e: st.error(f"Error displaying border table: {e}")
    else: st.info("No detailed border data.")

# ------------------------------------------
# Main Execution
# ------------------------------------------
folder_name = selected_scen_key.lower().replace(" ", "_")
result_dir = os.path.join(config.OUTPUT_DIR, folder_name)
existing_kpi_path = os.path.join(result_dir, 'kpi.json')
existing_map_path = os.path.join(result_dir, f'{folder_name}_map.html')
has_existing_data = os.path.exists(existing_kpi_path)

col_run, col_status = st.columns([1, 4])
with col_run:
    btn_label = "🚀 Re-Run Analysis" if has_existing_data else "🚀 Run Analysis"
    run_btn = st.button(btn_label, type="primary", use_container_width=True)

with col_status:
    if has_existing_data and not run_btn:
        st.info(f"📂 Cached results found for `{selected_scen_key}`. Displaying directly.")
    elif not has_existing_data:
        st.warning("⚠️ No cached results found. Please click Run.")

if run_btn:
    run_scenario_config = {
        'name': st.session_state['scenario_storage'][selected_scen_key]['name'],
        'description': 'UI Run',
        'capacity_factors': user_cfs, 
        'load_scale': load_scale,
        'generation_costs': user_gen_costs, 
        'import_costs': user_border_costs
    }
    from powerflow.analysis.scenarios import SCENARIOS
    SCENARIOS[folder_name] = run_scenario_config
    run_scenario_config['name'] = folder_name

    status = st.empty()
    bar = st.progress(0)
    engine = opf.OPFEngine(base_net, external_grids)
    start_time = time.time()
    
    try:
        status.write(f"Running OPF for **{folder_name}**...")
        res_net, res_info, converged = engine.run_scenario(run_scenario_config)
        bar.progress(100)
        
        if converged:
            status.success(f"Converged in {time.time() - start_time:.2f}s")
            exporter = report_export.ReportGenerator(res_net)
            exporter.export_all(folder_name)
            viz = visualization.Visualizer()
            viz.create_map(res_net, res_info, result_folder=folder_name)
            with open(os.path.join(result_dir, 'kpi.json'), 'r') as f: kpi_data = json.load(f)
            show_results(kpi_data, existing_map_path, folder_name)
        else:
            status.error("OPF did not converge. Try adjusting Load or Import Prices.")
    except Exception as e:
        status.error(f"Error during execution: {e}")
        st.exception(e)
elif has_existing_data:
    try:
        with open(existing_kpi_path, 'r') as f: kpi_data = json.load(f)
        show_results(kpi_data, existing_map_path, folder_name)
    except Exception as e: st.error(f"Error loading cached data: {e}")