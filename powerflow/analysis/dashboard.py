"""
Visualizer - Generates interactive folium maps of the power grid.
FIXED: Added Batch Processing Mode (Run range of scenarios).
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
import traceback # 用于捕获详细错误

# ==========================================
# 1. Environment & Paths
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path: sys.path.insert(0, project_root)

from powerflow.analysis import config, grid_building, opf, visualization, report_export
from powerflow.analysis.scenarios import SCENARIOS as PRESET_SCENARIOS, DEFAULT_GEN_COSTS

# ==========================================
# 2. Page Config & CSS
# ==========================================
st.set_page_config(page_title="German Grid OPF Scenario Dashboard", layout="wide", page_icon="⚡")
st.markdown("""<style>
    div[data-testid="stVerticalBlock"] > div { margin-bottom: -0.5rem; }
    div.stNumberInput, div.stSlider { padding-bottom: 0rem; }
    .streamlit-expanderContent div { margin-bottom: 0rem !important; }
    [data-testid="stDataFrame"] { width: 100%; }
    .caption-text { font-size: 0.85em; color: #555; margin-top: -10px; margin-bottom: 10px; }
    .debug-text { font-size: 0.75em; color: #d63031; font-family: monospace; }
    .success-text { color: green; font-weight: bold; }
    .fail-text { color: red; font-weight: bold; }
</style>""", unsafe_allow_html=True)

st.title("⚡ German Transmission Grid OPF Dashboard")

# ==========================================
# 3. Helpers
# ==========================================
def normalize_key(key):
    if not isinstance(key, str): return "other"
    return key.lower().strip().replace('_', ' ').replace('-', ' ')

# ==========================================
# 4. Init State & Load Grid
# ==========================================
if 'scenario_storage' not in st.session_state:
    st.session_state['scenario_storage'] = copy.deepcopy(PRESET_SCENARIOS)

if 'selected_scenario_name' not in st.session_state:
    st.session_state['selected_scenario_name'] = 'average_of_2025'

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
    base_net, ext_grids = modeler.create_base_network()
    
    neighbor_countries = set()
    for eg in ext_grids:
        if eg.get('type') != 'main_slack' and 'country' in eg:
            neighbor_countries.add(eg['country'])
    
    installed_cap = {}
    found_types_raw = set()

    for net_gen in [base_net.gen, base_net.sgen, base_net.storage]:
        if net_gen.empty: continue

        has_max_p = 'max_p_mw' in net_gen.columns
        has_type = 'type' in net_gen.columns
        has_name = 'name' in net_gen.columns 
        
        for _, row in net_gen.iterrows():
            raw_type = "unknown"
            if has_type and pd.notna(row['type']):
                raw_type = str(row['type'])
            elif has_name:
                raw_type = str(row['name']).split('_')[0]
            
            found_types_raw.add(raw_type)

            t = normalize_key(raw_type)
            if 'border' in t or 'ext' in t: continue
            
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
# 5. Sidebar: Config
# ==========================================
st.sidebar.header("🎛️ Scenario Configuration")

available_scenarios = list(st.session_state['scenario_storage'].keys())
idx = available_scenarios.index('average_of_2025') if 'average_of_2025' in available_scenarios else 0

selected_scen_key = st.sidebar.selectbox(
    "Select Scenario (Single Run)", options=available_scenarios, index=idx,
    format_func=lambda x: st.session_state['scenario_storage'][x]['name']
)

current_scen_data = st.session_state['scenario_storage'][selected_scen_key]
defaults_cf = current_scen_data.get('capacity_factors', {})
default_load_scale = current_scen_data.get('load_scale', 1.0)
defaults_gen_costs = current_scen_data.get('generation_costs', config.GENERATION_COSTS)
defaults_import_costs = current_scen_data.get('import_costs', config.IMPORT_COST_PARAMS)

st.sidebar.subheader("1. Demand Settings")
load_scale = st.sidebar.number_input("Global Load Scaling Factor", 0.5, 2.5, float(default_load_scale), 0.05)

st.sidebar.subheader("2. Generation Capacity Factors (CF)")

with st.sidebar.expander("Show/Hide Generators", expanded=True):
    master_gen_types = [k for k in DEFAULT_GEN_COSTS.keys() if k != 'default']
    user_cfs = {}
    for gen_type in master_gen_types:
        default_val = float(defaults_cf.get(gen_type, 0.0))
        
        lookup_key = normalize_key(gen_type)
        cap = installed_capacity_map.get(lookup_key, 0)
        if cap == 0:
             cap = installed_capacity_map.get(gen_type, 0)

        label_base = gen_type.replace('_', ' ').title()
        val = st.slider(f"{label_base}", 0.0, 1.0, default_val, 0.01, key=f"sl_{gen_type}")
        user_cfs[gen_type] = val
        
        current_mw = val * cap
        if cap > 0:
            st.markdown(f"<div class='caption-text'>⚡ <b>{current_mw:,.0f} MW</b> / {cap:,.0f} MW (Installed)</div>", unsafe_allow_html=True)

st.sidebar.subheader("3. Market Prices / Costs (€/MWh)")

with st.sidebar.expander("🏭 Domestic Generation Costs", expanded=False):
    user_gen_costs = {}
    for g_key in master_gen_types:
        default_global_cost = config.GENERATION_COSTS.get(g_key, 50)
        scen_cost = defaults_gen_costs.get(g_key, default_global_cost)
        label = g_key.replace('_', ' ').title()
        user_gen_costs[g_key] = st.number_input(f"{label}", value=float(scen_cost), step=1.0, key=f"cost_{g_key}")

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

st.sidebar.subheader("4. 🔋 Storage Strategy")
storage_mode_ui = st.sidebar.selectbox(
    "Select Operating Mode",
    ["Bidirectional (Flexible)", "Charge Only (Load)", "Discharge Only (Gen)"],
    index=0,
    help="Flexible: Can charge or discharge to fix congestion.\nCharge Only: Acts as load.\nDischarge Only: Acts as generator."
)
storage_mode_map = {
    "Bidirectional (Flexible)": "bidirectional",
    "Charge Only (Load)": "charge_only",
    "Discharge Only (Gen)": "discharge_only"
}
selected_storage_mode = storage_mode_map[storage_mode_ui]

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
            'import_costs': user_border_costs,
            'storage_mode': selected_storage_mode
        }
        st.session_state['scenario_storage'][safe_id] = new_entry
        st.success(f"Saved '{new_scen_name}'!")
        time.sleep(1)
        st.rerun()

# ==========================================
# 6. BATCH PROCESSING (NEW SECTION)
# ==========================================
st.sidebar.markdown("---")
st.sidebar.header("🚀 Batch Processing")
st.sidebar.info(f"Total Scenarios: {len(available_scenarios)}")

batch_col1, batch_col2 = st.sidebar.columns(2)
with batch_col1:
    start_idx = st.number_input("Start Index", min_value=0, max_value=len(available_scenarios)-1, value=0)
with batch_col2:
    end_idx = st.number_input("End Index", min_value=0, max_value=len(available_scenarios)-1, value=min(len(available_scenarios)-1, 1))

batch_run_btn = st.sidebar.button("▶️ Run Batch Sequence", type="primary")

# ==========================================
# 7. Helper: Show Results
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

    # Storage Analysis Panel
    s_kpi = kpi_data.get('storage_analysis', {})
    if s_kpi and s_kpi.get('installed_capacity_mw', 0) > 0:
        st.subheader("🔋 Storage Analysis")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Installed Cap", f"{s_kpi['installed_capacity_mw']:,.0f} MW")
        s2.metric("Available Cap", f"{s_kpi['available_capacity_mw']:,.0f} MW")
        s3.metric("Net Flow", f"{s_kpi['net_flow_mw']:,.0f} MW")
        s4.metric("Status (Units)", f"{s_kpi['charging_units']} Chg / {s_kpi['discharging_units']} Disch")
        st.divider()

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

# ------------------------------------------
# Main Execution Logic
# ------------------------------------------

# --- LOGIC 1: BATCH RUN ---
if batch_run_btn:
    st.header("🚀 Batch Processing Execution")
    
    if end_idx < start_idx:
        st.error("Error: End Index must be greater than or equal to Start Index.")
        st.stop()
        
    scenarios_to_run = available_scenarios[start_idx : end_idx + 1]
    total_batch = len(scenarios_to_run)
    
    st.write(f"Queue: **{total_batch}** scenarios (Index {start_idx} to {end_idx})")
    
    progress_bar = st.progress(0)
    status_box = st.empty()
    log_container = st.container()
    results_summary = []
    
    engine = opf.OPFEngine(base_net, external_grids)
    
    with log_container:
        for i, scen_key in enumerate(scenarios_to_run):
            idx_in_list = start_idx + i
            status_box.markdown(f"Running **{scen_key}** ({i+1}/{total_batch})...")
            
            t_start = time.time()
            folder_name = scen_key.lower().replace(" ", "_")
            
            # Prepare Config (Use stored config, not UI overrides for batch consistency)
            # You can change this to use UI overrides if you want them applied to ALL batch items
            scen_config = copy.deepcopy(st.session_state['scenario_storage'][scen_key])
            scen_config['name'] = folder_name
            
            run_status = "Unknown"
            duration = 0.0
            
            try:
                # Run OPF
                res_net, res_info, converged = engine.run_scenario(scen_config)
                duration = time.time() - t_start
                
                if converged:
                    run_status = "✅ Converged"
                    # Export Data
                    exporter = report_export.ReportGenerator(res_net)
                    exporter.export_all(folder_name)
                    viz = visualization.Visualizer()
                    viz.create_map(res_net, res_info, result_folder=folder_name)
                    
                    st.markdown(f"`[{idx_in_list}] {scen_key}`: <span class='success-text'>Converged</span> in {duration:.2f}s", unsafe_allow_html=True)
                else:
                    run_status = "❌ Failed (OPF)"
                    st.markdown(f"`[{idx_in_list}] {scen_key}`: <span class='fail-text'>Not Converged</span> ({duration:.2f}s) -> Skipping", unsafe_allow_html=True)
            
            except Exception as e:
                duration = time.time() - t_start
                run_status = "⚠️ Error"
                st.markdown(f"`[{idx_in_list}] {scen_key}`: <span class='fail-text'>Error: {str(e)}</span>", unsafe_allow_html=True)
                # traceback.print_exc() # Print to console if needed
            
            # Save Summary
            results_summary.append({
                "Index": idx_in_list,
                "Scenario": scen_key,
                "Status": run_status,
                "Time (s)": round(duration, 2)
            })
            
            # Update Progress
            progress_bar.progress((i + 1) / total_batch)
            
    status_box.success(f"Batch processing complete! ({total_batch} scenarios processed)")
    
    st.subheader("📝 Batch Summary")
    df_res = pd.DataFrame(results_summary)
    st.dataframe(df_res, use_container_width=True)


# --- LOGIC 2: SINGLE RUN (Original Logic) ---
else:
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
        # For Single Run, we use the UI overrides
        run_scenario_config = {
            'name': st.session_state['scenario_storage'][selected_scen_key]['name'],
            'description': 'UI Run',
            'capacity_factors': user_cfs, 
            'load_scale': load_scale,
            'generation_costs': user_gen_costs, 
            'import_costs': user_border_costs,
            'storage_mode': selected_storage_mode
        }
        # Update session storage temporarily for this run? 
        # Better to just pass config. The user can "Save Configuration" if they want permanence.
        
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