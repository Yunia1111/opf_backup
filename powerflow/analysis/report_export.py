"""
Report Generator - Exports OPF results to CSV, JSON and TXT.
MERGED VERSION: Original detailed exports + Dashboard KPI support.
FIXED: Added 'parallel' attribute to line export for correct capacity calculation.
"""
import pandas as pd
import os
import json
import numpy as np
from . import config
from .scenarios import SCENARIOS

class ReportGenerator:
    def __init__(self, net):
        self.net = net
        self.output_dir = config.OUTPUT_DIR
        
    def export_all(self, scenario_name):
        """Export all result files for a specific scenario."""
        safe_name = scenario_name
        self.output_dir = os.path.join(config.OUTPUT_DIR, safe_name)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 1. Export detailed CSVs
        self._export_bus_results()
        self._export_line_results()
        self._export_import_export_results()
        self._export_visualization_data()
        
        # 2. Export KPI and Summary
        kpi_data = self._calculate_consistent_kpi(scenario_name)
        
        with open(os.path.join(self.output_dir, 'kpi.json'), 'w') as f:
            json.dump(kpi_data, f)
            
        self._export_summary_txt(scenario_name, kpi_data)
        
        print(f"  ✓ Results exported to {self.output_dir}")

    def _calculate_consistent_kpi(self, scenario_name):
        """
        Core statistics: Ensures Total Gen = Sum(Mix), excludes imports.
        Adds detailed storage analysis.
        """
        total_load = self.net.res_load['p_mw'].sum() if len(self.net.res_load) > 0 else 0.0
        
        gen_mix = {}
        
        def process_source(element_type, res_table):
            if len(self.net[element_type]) == 0 or len(res_table) == 0: return
            
            # Merge static data and result data
            df = self.net[element_type].join(res_table[['p_mw']], rsuffix='_res')
            
            for idx, row in df.iterrows():
                p_val = row.get('p_mw_res', row.get('p_mw', 0))
                g_type = str(row.get('type', 'other')).lower()
                
                # Exclude border
                if 'border' in g_type: 
                    continue
                
                # Only positive output counts as generation
                if p_val > 0.001:
                    key = g_type
                    if element_type == 'ext_grid': key = 'balancing (slack)'
                    if element_type == 'storage': key = 'storage (discharge)'
                    gen_mix[key] = gen_mix.get(key, 0.0) + p_val

        process_source('gen', self.net.res_gen)
        process_source('sgen', self.net.res_sgen)
        process_source('storage', self.net.res_storage)
        process_source('ext_grid', self.net.res_ext_grid)
        
        total_gen = sum(gen_mix.values())
        
        # --- Storage Analysis ---
        storage_kpi = {
            'installed_capacity_mw': 0.0,
            'available_capacity_mw': 0.0,
            'net_flow_mw': 0.0,
            'charging_units': 0,
            'discharging_units': 0
        }
        
        if len(self.net.storage) > 0 and len(self.net.res_storage) > 0:
            # 1. Total Installed (Nameplate)
            if 'nameplate_p_mw' in self.net.storage.columns:
                storage_kpi['installed_capacity_mw'] = float(self.net.storage['nameplate_p_mw'].sum())
            else:
                # Fallback to current limits if nameplate missing (unlikely if built by grid_building)
                storage_kpi['installed_capacity_mw'] = float(self.net.storage['max_p_mw'].sum()) # Approximation

            # 2. Available Capacity (After CF application)
            # In opf.py, max_p_mw is set to Installed * CF
            storage_kpi['available_capacity_mw'] = float(self.net.storage['max_p_mw'].sum())
            
            # 3. Net Flow
            # +P = Discharge (Generation), -P = Charge (Load)
            net_flow = self.net.res_storage['p_mw'].sum()
            storage_kpi['net_flow_mw'] = float(net_flow)
            
            # 4. Units Count
            storage_kpi['discharging_units'] = int((self.net.res_storage['p_mw'] > 0.001).sum())
            storage_kpi['charging_units'] = int((self.net.res_storage['p_mw'] < -0.001).sum())

        return {
            'scenario': scenario_name,
            'total_load_mw': float(total_load),
            'total_gen_mw': float(total_gen),
            'total_cost_eur': float(self.net.res_cost) if hasattr(self.net, 'res_cost') else 0.0,
            'gen_by_type': gen_mix,
            'storage_analysis': storage_kpi
        }

    def _export_summary_txt(self, scenario_name, kpi_data):
        filepath = os.path.join(self.output_dir, 'summary.txt')
        total_gen = kpi_data['total_gen_mw']
        gen_mix = kpi_data['gen_by_type']
        line_losses = self.net.res_line['pl_mw'].sum() if len(self.net.res_line) > 0 else 0
        
        s_kpi = kpi_data.get('storage_analysis', {})

        scen_config = SCENARIOS.get(scenario_name, {})
        cfs = scen_config.get('capacity_factors', {})

        with open(filepath, 'w') as f:
            f.write(f"SCENARIO REPORT: {scenario_name.upper()}\n")
            f.write("="*60 + "\n\n")
            f.write(f"Total Cost:      {kpi_data['total_cost_eur']:,.2f} EUR/h\n")
            f.write(f"Total Load:      {kpi_data['total_load_mw']:,.2f} MW\n")
            f.write(f"Total Generation:{total_gen:,.2f} MW\n")
            f.write(f"Line Losses:     {line_losses:,.2f} MW\n\n")
            
            f.write("STORAGE ANALYSIS\n")
            f.write(f"  Installed Cap: {s_kpi.get('installed_capacity_mw',0):,.2f} MW\n")
            f.write(f"  Available Cap: {s_kpi.get('available_capacity_mw',0):,.2f} MW (CF applied)\n")
            f.write(f"  Net Flow:      {s_kpi.get('net_flow_mw',0):,.2f} MW (+Disch / -Charge)\n")
            f.write(f"  Units Status:  {s_kpi.get('charging_units',0)} Charging / {s_kpi.get('discharging_units',0)} Discharging\n\n")

            f.write("GENERATION MIX (Domestic)\n" + "-" * 68 + "\n")
            f.write(f"{'Type':<25} | {'Config CF':<10} | {'Output (MW)':>15} | {'Share':>8}\n")
            f.write("-" * 68 + "\n")
            
            for g_type, mw in sorted(gen_mix.items(), key=lambda x: x[1], reverse=True):
                cf_val = "N/A"
                for k, v in cfs.items():
                    if k in g_type: cf_val = f"{v:.2f}"; break
                share = (mw / total_gen * 100) if total_gen > 0 else 0
                f.write(f"{g_type:<25} | {cf_val:<10} | {mw:>15.2f} | {share:>7.1f}%\n")

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
        line_results['parallel'] = self.net.line['parallel']
        line_results.to_csv(os.path.join(self.output_dir, 'line_results.csv'), index=False)
        
        if len(self.net.res_line) > 0:
            overloaded = self.net.res_line[self.net.res_line['loading_percent'] > 100].copy()
            if not overloaded.empty:
                df = overloaded.merge(self.net.line[['name', 'from_bus', 'to_bus']], left_index=True, right_index=True)
                df.to_csv(os.path.join(self.output_dir, 'overload_report_lines.csv'), index=False)

    def _export_import_export_results(self):
        filepath_csv = os.path.join(self.output_dir, 'import_export_results.csv')
        export_data = []
        
        # 1. Main Slack (Ext Grid)
        for idx, eg in self.net.ext_grid.iterrows():
            if len(self.net.res_ext_grid) > 0:
                p_mw = self.net.res_ext_grid.at[idx, 'p_mw']
                direction = 'IMPORT' if p_mw > 0.001 else ('EXPORT' if p_mw < -0.001 else 'NEUTRAL')
                if direction != 'NEUTRAL':
                    export_data.append({
                        'name': eg.get('name', f'ExtGrid_{idx}'), 
                        'type': 'Main Slack',
                        'p_mw': p_mw, 
                        'q_mvar': self.net.res_ext_grid.at[idx, 'q_mvar'],
                        'direction': direction
                    })
            
        # 2. Border Connections (Gen type='border')
        if len(self.net.gen) > 0:
            border_gens = self.net.gen[self.net.gen['type'].astype(str) == 'border']
            for idx, gen in border_gens.iterrows():
                if len(self.net.res_gen) > 0:
                    p_mw = self.net.res_gen.at[idx, 'p_mw']
                    direction = 'IMPORT' if p_mw > 0.001 else ('EXPORT' if p_mw < -0.001 else 'NEUTRAL')
                    if direction != 'NEUTRAL':
                        export_data.append({
                            'name': gen['name'], 
                            'type': 'Border Connection',
                            'p_mw': p_mw, 
                            'q_mvar': self.net.res_gen.at[idx, 'q_mvar'],
                            'direction': direction
                        })
        
        if export_data:
            df = pd.DataFrame(export_data)
            df['abs_p'] = df['p_mw'].abs()
            df.sort_values(by='abs_p', ascending=False, inplace=True)
            df.drop(columns=['abs_p'], inplace=True)
            df.to_csv(filepath_csv, index=False, float_format='%.2f')

    def _export_visualization_data(self):
        """Exports data for map visualization."""
        d = {
            'buses': [], 'lines': [], 'generators': [], 'loads': [], 
            'external_grids': [], 'dclines': [], 'trafos': [], 'disconnected': [],
            'storage_units': [] 
        }

        get_geo = lambda i: self.net.bus.at[i, 'geo'] if self.net.bus.at[i, 'geo'] else None

        # Buses
        for i, b in self.net.bus.iterrows():
            geo = get_geo(i)
            if geo: 
                vm = float(self.net.res_bus.at[i, 'vm_pu']) if len(self.net.res_bus) > 0 else 1.0
                va = float(self.net.res_bus.at[i, 'va_degree']) if len(self.net.res_bus) > 0 else 0.0
                d['buses'].append({'id': i, 'name': b['name'], 'lat': geo[0], 'lon': geo[1], 'vn_kv': b['vn_kv'], 'vm_pu': vm, 'va_degree': va})   
        
        # Lines
        for i, l in self.net.line.iterrows():
            fgeo, tgeo = get_geo(l['from_bus']), get_geo(l['to_bus'])
            if fgeo and tgeo: 
                l_data = {
                    'id': i, 'name': l['name'], 
                    'from_bus_id': int(l['from_bus']), 'to_bus_id': int(l['to_bus']),
                    'from_lat': fgeo[0], 'from_lon': fgeo[1], 'to_lat': tgeo[0], 'to_lon': tgeo[1], 
                    'loading_percent': float(self.net.res_line.at[i, 'loading_percent']) if len(self.net.res_line) > 0 else 0.0, 
                    'p_from_mw': float(self.net.res_line.at[i, 'p_from_mw']) if len(self.net.res_line) > 0 else 0.0,
                    'q_from_mvar': float(self.net.res_line.at[i, 'q_from_mvar']) if len(self.net.res_line) > 0 else 0.0,
                    'p_to_mw': float(self.net.res_line.at[i, 'p_to_mw']) if len(self.net.res_line) > 0 else 0.0,
                    'q_to_mvar': float(self.net.res_line.at[i, 'q_to_mvar']) if len(self.net.res_line) > 0 else 0.0,
                    'max_i_ka': float(l.get('max_i_ka', 0.0)),
                    'parallel': int(l.get('parallel', 1)) 
                }
                if 'geo_coords' in l and pd.notna(l['geo_coords']): l_data['geo_coords'] = l['geo_coords']
                d['lines'].append(l_data)

        # Trafos
        for i, t in self.net.trafo.iterrows():
            hv_geo, lv_geo = get_geo(t['hv_bus']), get_geo(t['lv_bus'])
            if hv_geo: d['trafos'].append({'id': i, 'name': t['name'], 'hv_lat': hv_geo[0], 'hv_lon': hv_geo[1], 'lv_lat': lv_geo[0], 'lv_lon': lv_geo[1], 'loading_percent': float(self.net.res_trafo.at[i, 'loading_percent']) if len(self.net.res_trafo) > 0 else 0.0})
        
        # Generators (Split Gen/Sgen from Storage)
        for et in ['gen', 'sgen']:
            if len(self.net[et]) > 0:
                for i, g in self.net[et].iterrows():
                    geo = get_geo(g['bus'])
                    if geo: 
                        res_key = f'res_{et}'
                        p_val = self.net[res_key].at[i, 'p_mw'] if len(self.net[res_key]) > 0 else 0.0
                        q_val = self.net[res_key].at[i, 'q_mvar'] if len(self.net[res_key]) > 0 else 0.0
                        d['generators'].append({'id': f"{et}_{i}", 'name': g['name'], 'lat': geo[0], 'lon': geo[1], 'type': g['type'], 'p_mw': float(p_val), 'q_mvar': float(q_val)})

        # Storage Units
        if len(self.net.storage) > 0:
            for i, s in self.net.storage.iterrows():
                geo = get_geo(s['bus'])
                if geo:
                    p_val = self.net.res_storage.at[i, 'p_mw'] if len(self.net.res_storage) > 0 else 0.0
                    installed = s.get('nameplate_p_mw', s.get('max_p_mw', 0))
                    available = s.get('max_p_mw', 0)
                    d['storage_units'].append({
                        'id': f"storage_{i}", 'name': s['name'], 'lat': geo[0], 'lon': geo[1], 
                        'p_mw': float(p_val), 'installed_mw': float(installed), 
                        'available_mw': float(available)
                    })

        # Loads
        for i, l in self.net.load.iterrows():
            geo = get_geo(l['bus'])
            if geo: d['loads'].append({'id': i, 'name': l['name'], 'lat': geo[0], 'lon': geo[1], 'p_mw': float(l['p_mw']), 'q_mvar': float(l['q_mvar'])})

        # External Grids
        for i, eg in self.net.ext_grid.iterrows():
            geo = get_geo(eg['bus'])
            if geo: 
                p_val = self.net.res_ext_grid.at[i, 'p_mw'] if len(self.net.res_ext_grid) > 0 else 0
                q_val = self.net.res_ext_grid.at[i, 'q_mvar'] if len(self.net.res_ext_grid) > 0 else 0
                d['external_grids'].append({'id': i, 'name': eg['name'], 'lat': geo[0], 'lon': geo[1], 'p_mw': float(p_val), 'q_mvar': float(q_val)})

        # HVDC & DC Lines
        if len(self.net.dcline) > 0:
            for i, dc in self.net.dcline.iterrows():
                fgeo, tgeo = get_geo(dc['from_bus']), get_geo(dc['to_bus'])
                if fgeo:
                    p_val = self.net.res_dcline.at[i, 'p_from_mw'] if len(self.net.res_dcline) > 0 else 0
                    d['dclines'].append({'id': i, 'name': dc['name'], 'from_lat': fgeo[0], 'from_lon': fgeo[1], 'to_lat': tgeo[0], 'to_lon': tgeo[1], 'p_mw': float(p_val), 'capacity': float(dc['max_p_mw'])})
            
        # Disconnected
        disc_cache_path = os.path.join(config.OUTPUT_DIR, "disconnected_buses.json")
        if os.path.exists(disc_cache_path):
            try:
                with open(disc_cache_path, 'r') as f: d['disconnected'] = json.load(f)
            except: pass

        with open(os.path.join(self.output_dir, 'visualization_data.json'), 'w') as f:
            json.dump(d, f)