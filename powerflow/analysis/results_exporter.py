"""
Results Exporter - Export power flow results to CSV, JSON, and TXT files
"""
import pandas as pd
import os
import json
import config


class ResultsExporter:
    def __init__(self, net):
        self.net = net
        
    def export_all(self):
        """Export all result files"""
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        
        self._export_bus_results()
        self._export_line_results()
        self._export_transformer_results()
        self._export_overload_report()
        self._export_power_balance()
        self._export_summary()
        self._export_visualization_data()
        
        print(f"  ✓ Results exported to {config.OUTPUT_DIR}")
        
    def _export_bus_results(self):
        """Export bus voltage results"""
        bus_results = self.net.res_bus.copy()
        bus_results['bus_id'] = self.net.bus.index
        bus_results['name'] = self.net.bus['name']
        bus_results['vn_kv'] = self.net.bus['vn_kv']
        
        # Safely extract lat/lon from geo
        def get_lat(row):
            geo = self.net.bus.at[row.name, 'geo']
            return geo[0] if geo is not None and len(geo) == 2 else None
            
        def get_lon(row):
            geo = self.net.bus.at[row.name, 'geo']
            return geo[1] if geo is not None and len(geo) == 2 else None
        
        bus_results['lat'] = bus_results.apply(get_lat, axis=1)
        bus_results['lon'] = bus_results.apply(get_lon, axis=1)
        
        filepath = os.path.join(config.OUTPUT_DIR, 'bus_results.csv')
        bus_results.to_csv(filepath, index=False)
        
    def _export_line_results(self):
        """Export line results"""
        line_results = self.net.res_line.copy()
        line_results['line_id'] = self.net.line.index
        line_results['name'] = self.net.line['name']
        line_results['from_bus'] = self.net.line['from_bus']
        line_results['to_bus'] = self.net.line['to_bus']
        line_results['length_km'] = self.net.line['length_km']
        
        filepath = os.path.join(config.OUTPUT_DIR, 'line_results.csv')
        line_results.to_csv(filepath, index=False)
        
    def _export_transformer_results(self):
        """Export transformer results"""
        if len(self.net.trafo) == 0:
            return
            
        trafo_results = self.net.res_trafo.copy()
        trafo_results['trafo_id'] = self.net.trafo.index
        trafo_results['name'] = self.net.trafo['name']
        trafo_results['hv_bus'] = self.net.trafo['hv_bus']
        trafo_results['lv_bus'] = self.net.trafo['lv_bus']
        
        filepath = os.path.join(config.OUTPUT_DIR, 'transformer_results.csv')
        trafo_results.to_csv(filepath, index=False)
        
    def _export_overload_report(self):
        """Export overload report"""
        overloads = []
        
        # Check lines
        for idx, row in self.net.res_line.iterrows():
            if row['loading_percent'] > 100:
                overloads.append({
                    'type': 'Line',
                    'id': idx,
                    'name': self.net.line.at[idx, 'name'],
                    'loading_percent': row['loading_percent']
                })
                
        # Check transformers
        if len(self.net.trafo) > 0 and len(self.net.res_trafo) > 0:
            for idx, row in self.net.res_trafo.iterrows():
                if row['loading_percent'] > 100:
                    overloads.append({
                        'type': 'Transformer',
                        'id': idx,
                        'name': self.net.trafo.at[idx, 'name'],
                        'loading_percent': row['loading_percent']
                    })
                
        if len(overloads) > 0:
            df = pd.DataFrame(overloads)
            filepath = os.path.join(config.OUTPUT_DIR, 'overload_report.csv')
            df.to_csv(filepath, index=False)
            
    def _export_power_balance(self):
        """Export power balance analysis"""
        filepath = os.path.join(config.OUTPUT_DIR, 'power_balance.txt')
        
        with open(filepath, 'w') as f:
            f.write("POWER BALANCE ANALYSIS\n")
            f.write("="*60 + "\n\n")
            
            # Generation
            total_gen = 0
            if len(self.net.res_gen) > 0:
                gen_p = self.net.res_gen['p_mw'].sum()
                f.write(f"Generators (PV): {gen_p:.2f} MW\n")
                total_gen += gen_p
                
            if len(self.net.res_sgen) > 0:
                sgen_p = self.net.res_sgen['p_mw'].sum()
                f.write(f"Static Generators (PQ): {sgen_p:.2f} MW\n")
                total_gen += sgen_p
                
            if len(self.net.res_ext_grid) > 0:
                ext_p = self.net.res_ext_grid['p_mw'].sum()
                f.write(f"External Grids: {ext_p:.2f} MW\n")
                total_gen += ext_p
                
            f.write(f"TOTAL GENERATION: {total_gen:.2f} MW\n\n")
            
            # Load
            load_p = self.net.res_load['p_mw'].sum()
            f.write(f"Loads: {load_p:.2f} MW\n\n")
            
            # Losses
            line_losses = self.net.res_line['pl_mw'].sum()
            trafo_losses = self.net.res_trafo['pl_mw'].sum() if len(self.net.res_trafo) > 0 else 0
            total_losses = line_losses + trafo_losses
            
            f.write(f"Line losses: {line_losses:.2f} MW\n")
            f.write(f"Transformer losses: {trafo_losses:.2f} MW\n")
            f.write(f"TOTAL LOSSES: {total_losses:.2f} MW ({total_losses/load_p*100:.2f}%)\n\n")
            
            # Balance
            balance = total_gen - load_p - total_losses
            f.write(f"Balance (should be ~0): {balance:.2f} MW\n")
            
    def _export_summary(self):
        """Export summary report"""
        filepath = os.path.join(config.OUTPUT_DIR, 'summary.txt')
        
        with open(filepath, 'w') as f:
            f.write("POWER FLOW SUMMARY\n")
            f.write("="*60 + "\n\n")
            
            f.write(f"Buses: {len(self.net.bus)}\n")
            f.write(f"Lines: {len(self.net.line)}\n")
            f.write(f"Transformers: {len(self.net.trafo)}\n")
            f.write(f"Generators: {len(self.net.gen)} PV + {len(self.net.sgen)} PQ\n")
            f.write(f"Loads: {len(self.net.load)}\n\n")
            
            f.write("VOLTAGE STATISTICS:\n")
            f.write(f"Min: {self.net.res_bus['vm_pu'].min():.4f} pu\n")
            f.write(f"Max: {self.net.res_bus['vm_pu'].max():.4f} pu\n")
            f.write(f"Avg: {self.net.res_bus['vm_pu'].mean():.4f} pu\n\n")
            
            if len(self.net.res_line) > 0:
                f.write("LOADING STATISTICS:\n")
                f.write(f"Max line loading: {self.net.res_line['loading_percent'].max():.1f}%\n")
                overloaded = (self.net.res_line['loading_percent'] > 100).sum()
                f.write(f"Overloaded lines: {overloaded}\n")
                
    def _export_visualization_data(self):
        """Export data for visualization"""
        vis_data = {
            'buses': [],
            'lines': [],
            'generators': [],
            'loads': [],
            'external_grids': []
        }
        
        # Buses
        for idx, bus in self.net.bus.iterrows():
            geo = bus.get('geo')
            if geo is not None and len(geo) == 2:
                lat, lon = geo
                vis_data['buses'].append({
                    'id': idx,
                    'name': bus['name'],
                    'lat': lat,
                    'lon': lon,
                    'vn_kv': bus['vn_kv'],
                    'vm_pu': float(self.net.res_bus.at[idx, 'vm_pu']),
                    'va_degree': float(self.net.res_bus.at[idx, 'va_degree'])
                })
        
        # Lines
        for idx, line in self.net.line.iterrows():
            from_bus = line['from_bus']
            to_bus = line['to_bus']
            
            from_geo = self.net.bus.at[from_bus, 'geo']
            to_geo = self.net.bus.at[to_bus, 'geo']
            
            if (from_geo is not None and len(from_geo) == 2 and 
                to_geo is not None and len(to_geo) == 2):
                
                from_lat, from_lon = from_geo
                to_lat, to_lon = to_geo
                
                line_data = {
                    'id': idx,
                    'name': line['name'],
                    'from_bus_id': from_bus,
                    'to_bus_id': to_bus,
                    'from_lat': from_lat,
                    'from_lon': from_lon,
                    'to_lat': to_lat,
                    'to_lon': to_lon,
                    'loading_percent': float(self.net.res_line.at[idx, 'loading_percent']),
                    'p_from_mw': float(self.net.res_line.at[idx, 'p_from_mw']),
                    'q_from_mvar': float(self.net.res_line.at[idx, 'q_from_mvar']),
                    'i_from_ka': float(self.net.res_line.at[idx, 'i_from_ka']),
                    'parallel': int(line['parallel']),
                    'cables_per_phase': int(line.get('cables_per_phase', 1)),
                    'length_km': float(line['length_km']),
                    'max_i_ka': float(line['max_i_ka']),
                    'r_ohm_per_km': float(line['r_ohm_per_km']),
                    'x_ohm_per_km': float(line['x_ohm_per_km']),
                    'c_nf_per_km': float(line['c_nf_per_km'])
                }
                
                # Add geographic coordinates if available
                if 'geo_coords' in line and pd.notna(line['geo_coords']):
                    import ast
                    try:
                        coords = ast.literal_eval(line['geo_coords'])
                        line_data['geo_coords'] = coords
                    except:
                        pass
                
                vis_data['lines'].append(line_data)
        
        # Generators
        for idx, gen in self.net.gen.iterrows():
            bus_idx = gen['bus']
            geo = self.net.bus.at[bus_idx, 'geo']
            if geo is not None and len(geo) == 2:
                lat, lon = geo
                vis_data['generators'].append({
                    'id': idx,
                    'name': gen['name'],
                    'lat': lat,
                    'lon': lon,
                    'type': gen['type'],
                    'p_mw': float(self.net.res_gen.at[idx, 'p_mw']),
                    'sn_mva': float(gen['sn_mva'])
                })
        
        # Also add static generators (PQ)
        for idx, gen in self.net.sgen.iterrows():
            bus_idx = gen['bus']
            geo = self.net.bus.at[bus_idx, 'geo']
            if geo is not None and len(geo) == 2:
                lat, lon = geo
                vis_data['generators'].append({
                    'id': f"sgen_{idx}",
                    'name': gen['name'],
                    'lat': lat,
                    'lon': lon,
                    'type': gen['type'],
                    'p_mw': float(self.net.res_sgen.at[idx, 'p_mw']),
                    'sn_mva': float(gen['sn_mva'])
                })
        
        # Loads
        for idx, load in self.net.load.iterrows():
            bus_idx = load['bus']
            geo = self.net.bus.at[bus_idx, 'geo']
            if geo is not None and len(geo) == 2:
                lat, lon = geo
                vis_data['loads'].append({
                    'id': idx,
                    'name': load['name'],
                    'lat': lat,
                    'lon': lon,
                    'p_mw': float(self.net.res_load.at[idx, 'p_mw']),
                    'q_mvar': float(self.net.res_load.at[idx, 'q_mvar'])
                })
                
        # External grids
        for idx, ext_grid in self.net.ext_grid.iterrows():
            bus_idx = ext_grid['bus']
            geo = self.net.bus.at[bus_idx, 'geo']
            if geo is not None and len(geo) == 2:
                lat, lon = geo
                vis_data['external_grids'].append({
                    'id': idx,
                    'name': ext_grid['name'],
                    'lat': lat,
                    'lon': lon,
                    'p_mw': float(self.net.res_ext_grid.at[idx, 'p_mw']),
                    'q_mvar': float(self.net.res_ext_grid.at[idx, 'q_mvar'])
                })
                
        filepath = os.path.join(config.OUTPUT_DIR, 'visualization_data.json')
        with open(filepath, 'w') as f:
            json.dump(vis_data, f, indent=2)