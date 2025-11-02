"""
Network Validity Checker - Pre-power-flow checks and data validation
SIMPLIFIED VERSION - Minimal output
"""
import pandas as pd
import numpy as np
import pandapower.topology as top
import networkx as nx


class NetworkValidityChecker:
    def __init__(self, net):
        self.net = net
        self.issues_found = []
        self.skipped_elements = {
            'lines': [],
            'transformers': [],
            'generators': []
        }
        
    def check_and_clean(self):
        """Run all pre-power-flow checks and clean problematic data"""
        print("\nSTEP 5: Network validity check")
        
        # Run all checks (silent)
        self._check_islands()
        self._check_zero_impedance_lines()
        self._check_transformer_issues()
        self._check_external_grid_conflicts()
        self._check_generator_voltage_conflicts()
        self._check_power_balance()
        
        # Print summary
        self._print_summary()
        
        is_valid = len(self.issues_found) == 0
        
        summary = {
            'is_valid': is_valid,
            'issues_count': len(self.issues_found),
            'issues': self.issues_found,
            'skipped_elements': self.skipped_elements,
            'network_stats': {
                'buses': len(self.net.bus),
                'lines': len(self.net.line),
                'transformers': len(self.net.trafo),
                'pv_generators': len(self.net.gen),
                'pq_generators': len(self.net.sgen),
                'loads': len(self.net.load),
                'external_grids': len(self.net.ext_grid)
            }
        }
        
        return is_valid, summary
        
    def _check_islands(self):
        """Check for isolated network components (islands)"""
        try:
            mg = top.create_nxgraph(self.net, respect_switches=False)
            components = list(nx.connected_components(mg))
            
            if len(components) == 1:
                return
            
            # Remove islands
            main_component = max(components, key=len)
            buses_to_keep = set(main_component)
            isolated_buses = set(self.net.bus.index) - buses_to_keep
            
            # Filter all elements
            self.net.bus = self.net.bus[self.net.bus.index.isin(buses_to_keep)]
            self.net.line = self.net.line[
                (self.net.line['from_bus'].isin(buses_to_keep)) & 
                (self.net.line['to_bus'].isin(buses_to_keep))
            ]
            self.net.trafo = self.net.trafo[
                (self.net.trafo['hv_bus'].isin(buses_to_keep)) & 
                (self.net.trafo['lv_bus'].isin(buses_to_keep))
            ]
            self.net.gen = self.net.gen[self.net.gen['bus'].isin(buses_to_keep)]
            self.net.sgen = self.net.sgen[self.net.sgen['bus'].isin(buses_to_keep)]
            self.net.load = self.net.load[self.net.load['bus'].isin(buses_to_keep)]
            self.net.ext_grid = self.net.ext_grid[self.net.ext_grid['bus'].isin(buses_to_keep)]
            
            self.issues_found.append(f"Removed {len(components)-1} islands ({len(isolated_buses)} buses)")
            
        except Exception as e:
            self.issues_found.append(f"Connectivity check failed: {e}")
            
    def _check_zero_impedance_lines(self):
        """Check for lines with near-zero or zero impedance"""
        if len(self.net.line) == 0:
            return
        
        r_total = self.net.line['r_ohm_per_km'] * self.net.line['length_km']
        x_total = self.net.line['x_ohm_per_km'] * self.net.line['length_km']
        
        zero_impedance = (r_total == 0) & (x_total == 0)
        very_low_r = r_total < 1e-6
        very_low_x = x_total < 1e-6
        
        problematic = zero_impedance | (very_low_r & very_low_x)
        n_problematic = problematic.sum()
        
        if n_problematic == 0:
            return
        
        # Skip these lines
        problematic_lines = self.net.line[problematic]
        for idx, line in problematic_lines.iterrows():
            line_info = {
                'index': idx,
                'name': line.get('name', 'N/A'),
                'r_total': r_total.loc[idx],
                'x_total': x_total.loc[idx]
            }
            self.skipped_elements['lines'].append(line_info)
        
        self.net.line = self.net.line[~problematic]
        self.issues_found.append(f"Skipped {n_problematic} lines with near-zero impedance")
        
    def _check_transformer_issues(self):
        """Check for transformers connecting same voltage levels"""
        if len(self.net.trafo) == 0:
            return
        
        same_voltage_trafos = []
        zero_sn_trafos = []
        
        for idx, trafo in self.net.trafo.iterrows():
            hv_vn = self.net.bus.at[trafo['hv_bus'], 'vn_kv']
            lv_vn = self.net.bus.at[trafo['lv_bus'], 'vn_kv']
            
            if hv_vn == lv_vn:
                same_voltage_trafos.append(idx)
                trafo_info = {
                    'index': idx,
                    'name': trafo.get('name', 'N/A'),
                    'voltage': hv_vn,
                    'reason': 'same_voltage_level'
                }
                self.skipped_elements['transformers'].append(trafo_info)
            
            if trafo.get('sn_mva', 0) == 0:
                zero_sn_trafos.append(idx)
                if idx not in same_voltage_trafos:
                    trafo_info = {
                        'index': idx,
                        'name': trafo.get('name', 'N/A'),
                        'reason': 'zero_rated_power'
                    }
                    self.skipped_elements['transformers'].append(trafo_info)
        
        problematic_trafos = list(set(same_voltage_trafos + zero_sn_trafos))
        
        if len(problematic_trafos) > 0:
            self.net.trafo = self.net.trafo.drop(problematic_trafos)
            
            if len(same_voltage_trafos) > 0:
                self.issues_found.append(f"Skipped {len(same_voltage_trafos)} transformers (same voltage)")
            
            if len(zero_sn_trafos) > 0:
                self.issues_found.append(f"Skipped {len(zero_sn_trafos)} transformers (zero rating)")
            
    def _check_external_grid_conflicts(self):
        """Check for PV generators on external grid buses"""
        ext_grid_buses = set(self.net.ext_grid['bus'].tolist())
        
        # Check for duplicate external grids
        ext_grid_bus_counts = pd.Series(list(ext_grid_buses)).value_counts()
        duplicates = ext_grid_bus_counts[ext_grid_bus_counts > 1]
        
        if len(duplicates) > 0:
            self.issues_found.append(f"{len(duplicates)} buses have duplicate external grids")
        
        # Check PV generators on ext_grid buses
        if len(self.net.gen) > 0:
            gen_buses = set(self.net.gen['bus'].tolist())
            conflicts = gen_buses & ext_grid_buses
            
            if len(conflicts) > 0:
                conflicting_gens = self.net.gen[self.net.gen['bus'].isin(conflicts)]
                
                for idx, gen in conflicting_gens.iterrows():
                    gen_info = {
                        'index': idx,
                        'name': gen.get('name', 'N/A'),
                        'bus': gen['bus'],
                        'reason': 'on_external_grid_bus'
                    }
                    self.skipped_elements['generators'].append(gen_info)
                
                self.net.gen = self.net.gen[~self.net.gen['bus'].isin(conflicts)]
                self.issues_found.append(f"Removed {len(conflicts)} PV generators (on ext_grid buses)")
            
    def _check_generator_voltage_conflicts(self):
        """Check for generators with different voltage setpoints on same bus"""
        if len(self.net.gen) == 0:
            return
        
        gen_grouped = self.net.gen.groupby('bus')['vm_pu'].agg(['count', 'nunique'])
        conflicts = gen_grouped[gen_grouped['nunique'] > 1]
        
        if len(conflicts) > 0:
            for bus_idx, row in conflicts.iterrows():
                gens_on_bus = self.net.gen[self.net.gen['bus'] == bus_idx]
                mean_vm = gens_on_bus['vm_pu'].mean()
                self.net.gen.loc[self.net.gen['bus'] == bus_idx, 'vm_pu'] = mean_vm
            
            self.issues_found.append(f"{len(conflicts)} buses had conflicting voltage setpoints (resolved)")
            
    def _check_power_balance(self):
        """Check generation vs load balance"""
        total_gen = 0
        if len(self.net.gen) > 0:
            total_gen += self.net.gen['p_mw'].sum()
        if len(self.net.sgen) > 0:
            total_gen += self.net.sgen['p_mw'].sum()
        
        total_load = self.net.load['p_mw'].sum()
        
        if total_load == 0:
            self.issues_found.append("Total load is zero")
            return
        
        balance_ratio = total_gen / total_load
        
        if balance_ratio < 0.90:
            self.issues_found.append(f"Generation at {balance_ratio*100:.1f}% of load")
        elif balance_ratio > 1.20:
            self.issues_found.append(f"Generation at {balance_ratio*100:.1f}% of load")
            
    def _print_summary(self):
        """Print check summary"""
        if len(self.issues_found) == 0:
            print("  ✓ All checks passed")
        else:
            print(f"  ⚠ {len(self.issues_found)} issues handled automatically")