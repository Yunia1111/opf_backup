"""
Report Generator - Exports OPF results to CSV, JSON and TXT.
Features: Detailed Energy Mix, Import/Export, and NEW HVDC Summary.
FIX: Added safety checks for 'tap_phase_shifter' column to prevent KeyErrors.
"""
import pandas as pd
import os
import json
import config
try:
    from scenarios import SCENARIOS # Updated Import
except ImportError:
    SCENARIOS = {}

class ReportGenerator:
    def __init__(self, net):
        self.net = net
        self.output_dir = config.OUTPUT_DIR
        
    def export_all(self, scenario_name):
        """Export all result files for a specific scenario."""
        self.output_dir = os.path.join(config.OUTPUT_DIR, scenario_name) + os.sep
        os.makedirs(self.output_dir, exist_ok=True)
        
        self._export_bus_results()
        self._export_line_results()
        self._export_import_export_results()
        self._export_summary(scenario_name)
        self._export_visualization_data()
        
        print(f"  ✓ Results exported to {self.output_dir}")
        
    def _export_bus_results(self):
        bus_results = self.net.res_bus.copy()
        bus_results['bus_id'] = self.net.bus.index
        bus_results['name'] = self.net.bus['name']
        bus_results['vn_kv'] = self.net.bus['vn_kv']
        bus_results.to_csv(os.path.join(self.output_dir, 'bus_results.csv'), index=False)
        
    def _export_line_results(self):
        line_results = self.net.res_line.copy()
        line_results['line_id'] = self.net.line.index
        line_results['name'] = self.net.line['name']
        line_results['from_bus'] = self.net.line['from_bus']
        line_results['to_bus'] = self.net.line['to_bus']
        line_results.to_csv(os.path.join(self.output_dir, 'line_results.csv'), index=False)
        
        if len(self.net.res_line) > 0:
            overloaded = self.net.res_line[self.net.res_line['loading_percent'] > 100].copy()
            if not overloaded.empty:
                df = overloaded.merge(self.net.line[['name', 'from_bus', 'to_bus']], left_index=True, right_index=True)
                df.to_csv(os.path.join(self.output_dir, 'overload_report_lines.csv'), index=False)

    def _export_import_export_results(self):
        filepath_csv = os.path.join(self.output_dir, 'import_export_results.csv')
        export_data = []
        
        # 1. Main Slack
        for idx, eg in self.net.ext_grid.iterrows():
            if len(self.net.res_ext_grid) > 0:
                p_mw = self.net.res_ext_grid.at[idx, 'p_mw']
                export_data.append({
                    'name': eg.get('name', f'ExtGrid_{idx}'), 'type': 'Main Slack',
                    'p_mw': p_mw, 'q_mvar': self.net.res_ext_grid.at[idx, 'q_mvar'],
                    'direction': 'IMPORT' if p_mw > 0 else 'EXPORT'
                })
            
        # 2. Border Connections
        if len(self.net.gen) > 0:
            border_gens = self.net.gen[self.net.gen['type'].astype(str) == 'border']
            for idx, gen in border_gens.iterrows():
                if len(self.net.res_gen) > 0:
                    p_mw = self.net.res_gen.at[idx, 'p_mw']
                    export_data.append({
                        'name': gen['name'], 'type': 'Border Connection',
                        'p_mw': p_mw, 'q_mvar': self.net.res_gen.at[idx, 'q_mvar'],
                        'direction': 'IMPORT' if p_mw > 0 else 'EXPORT'
                    })
        
        if export_data:
            df = pd.DataFrame(export_data)
            df['abs_p'] = df['p_mw'].abs()
            df.sort_values(by='abs_p', ascending=False, inplace=True)
            df.drop(columns=['abs_p'], inplace=True)
            df.to_csv(filepath_csv, index=False, float_format='%.2f')
            
    def _export_summary(self, scenario_name):
        filepath = os.path.join(self.output_dir, 'summary.txt')
        
        total_cost = self.net.res_cost if hasattr(self.net, 'res_cost') else 0
        total_load = self.net.load['p_mw'].sum()
        line_losses = self.net.res_line['pl_mw'].sum() if len(self.net.res_line) > 0 else 0
        
        # Generation Mix
        gen_mix = {}
        def sum_by_type(element_type, res_table):
            if len(self.net[element_type]) == 0: return
            if len(res_table) == 0: return
            df = self.net[element_type].join(res_table[['p_mw']], rsuffix='_res')
            if 'type' in df.columns:
                df = df[df['type'].astype(str) != 'border']
            p_col = 'p_mw_res' if 'p_mw_res' in df.columns else 'p_mw'
            if p_col in df.columns:
                grouped = df.groupby('type')[p_col].sum()
                for k, v in grouped.items(): gen_mix[str(k).lower()] = gen_mix.get(str(k).lower(), 0) + v

        sum_by_type('gen', self.net.res_gen)
        sum_by_type('sgen', self.net.res_sgen)
        
        # Storage logic
        storage_p = self.net.res_storage['p_mw'] if len(self.net.res_storage) > 0 else pd.Series(dtype=float)
        discharge = storage_p[storage_p > 0].sum()
        charge = abs(storage_p[storage_p < 0].sum())
        
        if discharge > 0: gen_mix['storage (discharge)'] = discharge
        
        total_gen = sum(gen_mix.values())
        scen_config = SCENARIOS.get(scenario_name, {})
        cfs = scen_config.get('capacity_factors', {})

        with open(filepath, 'w') as f:
            f.write(f"SCENARIO REPORT: {scenario_name.upper()}\n")
            f.write("="*60 + "\n\n")
            f.write(f"Total Cost:      {total_cost:,.2f} EUR/h\n")
            f.write(f"Total Load:      {total_load:,.2f} MW\n")
            f.write(f"Total Generation:{total_gen:,.2f} MW\n")
            if charge > 0.1:
                f.write(f"Storage Charge:  {charge:,.2f} MW\n")
            f.write(f"Line Losses:     {line_losses:,.2f} MW\n\n")
            
            f.write("GENERATION MIX\n" + "-" * 68 + "\n")
            f.write(f"{'Type':<25} | {'Config CF':<10} | {'Output (MW)':>15} | {'Share':>8}\n")
            f.write("-" * 68 + "\n")
            for g_type, mw in sorted(gen_mix.items(), key=lambda x: x[1], reverse=True):
                cf_val = "N/A"
                for k, v in cfs.items():
                    if k in g_type: cf_val = f"{v:.2f}"; break
                f.write(f"{g_type:<25} | {cf_val:<10} | {mw:>15.2f} | {(mw/total_gen*100):>7.1f}%\n")
            
            # HVDC SECTION
            f.write("\n\nHVDC CORRIDOR UTILIZATION\n")
            f.write("-" * 68 + "\n")
            f.write(f"{'Name':<25} | {'Flow (MW)':>15} | {'Capacity':>10} | {'Util %':>8}\n")
            f.write("-" * 68 + "\n")
            if len(self.net.dcline) > 0:
                for idx, dc in self.net.dcline.iterrows():
                    if len(self.net.res_dcline) > 0:
                        p_mw = self.net.res_dcline.at[idx, 'p_from_mw']
                    else:
                        p_mw = 0.0
                    cap = dc['max_p_mw']
                    util = abs(p_mw) / cap * 100 if cap > 0 else 0
                    f.write(f"{dc['name']:<25} | {p_mw:>15.1f} | {cap:>10.0f} | {util:>7.1f}%\n")
            else:
                f.write("No HVDC lines configured.\n")

            # PST SECTION
            f.write("\n\nPHASE SHIFT TRANSFORMERS (PST)\n")
            f.write("-" * 68 + "\n")
            f.write(f"{'Name':<25} | {'Angle (Deg)':>12} | {'Loading %':>10}\n")
            f.write("-" * 68 + "\n")
            
            # [FIXED] Safely check for tap_phase_shifter column
            if 'tap_phase_shifter' in self.net.trafo.columns:
                pst_trafos = self.net.trafo[self.net.trafo['tap_phase_shifter'] == True]
            else:
                pst_trafos = pd.DataFrame()

            if not pst_trafos.empty:
                for idx, t in pst_trafos.iterrows():
                    # Calculate actual angle: tap_pos * tap_step_degree
                    angle = self.net.res_trafo.at[idx, 'tap_pos'] * t['tap_step_degree'] if idx in self.net.res_trafo.index else 0
                    loading = self.net.res_trafo.at[idx, 'loading_percent'] if idx in self.net.res_trafo.index else 0
                    f.write(f"{t['name']:<25} | {angle:>12.1f} | {loading:>10.1f}\n")
            else:
                f.write("No PSTs active.\n")

    def _export_visualization_data(self):
        d = {'buses': [], 'lines': [], 'generators': [], 'loads': [], 'external_grids': [], 'dclines': [], 'psts': [], 'disconnected': []}
        get_geo = lambda i: self.net.bus.at[i, 'geo'] if self.net.bus.at[i, 'geo'] else None
        
        for i, b in self.net.bus.iterrows():
            geo = get_geo(i)
            if geo: d['buses'].append({'id': i, 'name': b['name'], 'lat': geo[0], 'lon': geo[1], 'vn_kv': b['vn_kv'], 'vm_pu': float(self.net.res_bus.at[i, 'vm_pu'])})
            
        for i, l in self.net.line.iterrows():
            fgeo, tgeo = get_geo(l['from_bus']), get_geo(l['to_bus'])
            if fgeo: 
                l_data = {'id': i, 'name': l['name'], 'from_bus_id': l['from_bus'], 'to_bus_id': l['to_bus'], 'from_lat': fgeo[0], 'from_lon': fgeo[1], 'to_lat': tgeo[0], 'to_lon': tgeo[1], 'loading_percent': float(self.net.res_line.at[i, 'loading_percent']), 'p_from_mw': float(self.net.res_line.at[i, 'p_from_mw'])}
                if 'geo_coords' in l and pd.notna(l['geo_coords']):
                    try: l_data['geo_coords'] = __import__('ast').literal_eval(l['geo_coords'])
                    except: pass
                d['lines'].append(l_data)
        
        # HVDC
        if len(self.net.dcline) > 0:
            for i, dc in self.net.dcline.iterrows():
                fgeo, tgeo = get_geo(dc['from_bus']), get_geo(dc['to_bus'])
                if fgeo:
                    p_val = self.net.res_dcline.at[i, 'p_from_mw'] if len(self.net.res_dcline) > 0 else 0
                    d['dclines'].append({'id': i, 'name': dc['name'], 'from_lat': fgeo[0], 'from_lon': fgeo[1], 'to_lat': tgeo[0], 'to_lon': tgeo[1], 'p_mw': float(p_val), 'capacity': float(dc['max_p_mw'])})

        # PSTs
        # [FIXED] Safely check for tap_phase_shifter column
        if 'tap_phase_shifter' in self.net.trafo.columns:
            pst_trafos = self.net.trafo[self.net.trafo['tap_phase_shifter'] == True]
        else:
            pst_trafos = pd.DataFrame()

        for idx, t in pst_trafos.iterrows():
            geo = self.net.bus.at[t['hv_bus'], 'geo'] # Plot at HV side
            if geo:
                tap_pos = float(self.net.res_trafo.at[idx, 'tap_pos']) if idx in self.net.res_trafo.index else 0
                angle = tap_pos * float(t['tap_step_degree'])
                load = float(self.net.res_trafo.at[idx, 'loading_percent']) if idx in self.net.res_trafo.index else 0
                d['psts'].append({'id': idx, 'name': t['name'], 'lat': geo[0], 'lon': geo[1], 'tap_pos': angle, 'loading': load})

        for et in ['gen', 'sgen', 'storage']:
            if len(self.net[et]) > 0:
                for i, g in self.net[et].iterrows():
                    geo = get_geo(g['bus'])
                    res_key = f'res_{et}'
                    p_val = self.net[res_key].at[i, 'p_mw'] if len(self.net[res_key]) > 0 else 0
                    if geo: d['generators'].append({'id': f"{et}_{i}", 'name': g['name'], 'lat': geo[0], 'lon': geo[1], 'type': g['type'], 'p_mw': float(p_val), 'sn_mva': float(g.get('sn_mva', 0))})
                    
        for i, eg in self.net.ext_grid.iterrows():
            geo = get_geo(eg['bus'])
            p_val = self.net.res_ext_grid.at[i, 'p_mw'] if len(self.net.res_ext_grid) > 0 else 0
            if geo: d['external_grids'].append({'id': i, 'name': eg['name'], 'lat': geo[0], 'lon': geo[1], 'p_mw': float(p_val)})
            
        # [NEW] Add Disconnected Buses
        disc_cache_path = os.path.join(config.OUTPUT_DIR, "disconnected_buses.json")
        if os.path.exists(disc_cache_path):
            try:
                with open(disc_cache_path, 'r') as f:
                    d['disconnected'] = json.load(f)
            except: pass
            
        with open(os.path.join(self.output_dir, 'visualization_data.json'), 'w') as f: json.dump(d, f)