"""
Network builder - creates pandapower network from preprocessed data
"""
import pandapower as pp
import pandas as pd
import config


class NetworkBuilder:
    def __init__(self, preprocessor, external_grids):
        self.buses = preprocessor.buses
        self.connections = preprocessor.connections
        self.generators = preprocessor.generators
        self.loads = preprocessor.loads
        self.transformers = preprocessor.transformers
        self.external_grids = external_grids
        self.net = None
        self.bus_mapping = {}
        
    def build_network(self):
        """Build complete pandapower network"""
        self.net = pp.create_empty_network(name="German Grid")
        
        self._add_buses()
        self._add_external_grids()
        self._add_lines()
        self._add_transformers()
        self._add_generators()
        self._add_loads()
        
        print(f"Network built: {len(self.net.bus)} buses, {len(self.net.line)} lines, "
              f"{len(self.net.gen)} PV gens, {len(self.net.sgen)} PQ gens, "
              f"{len(self.net.load)} loads")
        return self.net
        
    def _add_buses(self):
        """Add all buses"""
        for _, bus in self.buses.iterrows():
            idx = pp.create_bus(
                self.net,
                vn_kv=bus['vn_kv'],
                name=bus['name'],
                geodata=(bus['lat'], bus['lon'])
            )
            self.bus_mapping[bus['bus_id']] = idx
            
            # Also store in bus table for easy access
            self.net.bus.at[idx, 'geo'] = (bus['lat'], bus['lon'])
            
    def _add_external_grids(self):
        """Add external grids (slack buses)"""
        for eg in self.external_grids:
            bus_idx = self.bus_mapping[eg['bus_id']]
            pp.create_ext_grid(
                self.net,
                bus=bus_idx,
                vm_pu=eg['vm_pu'],
                va_degree=eg['va_degree'] if eg['va_degree'] is not None else 0.0,
                max_p_mw=eg['max_p_mw'],
                min_p_mw=eg['min_p_mw'],
                name=f"ExtGrid_{eg['country']}"
            )
            
    def _add_lines(self):
        """Add all transmission lines"""
        for _, line in self.connections.iterrows():
            from_bus = self.bus_mapping.get(line['from_bus_id'])
            to_bus = self.bus_mapping.get(line['to_bus_id'])
            
            if from_bus is None or to_bus is None:
                continue
                
            line_idx = pp.create_line_from_parameters(
                self.net,
                from_bus=from_bus,
                to_bus=to_bus,
                length_km=line['length_km'],
                r_ohm_per_km=line['r_ohm_per_km'],
                x_ohm_per_km=line['x_ohm_per_km'],
                c_nf_per_km=line['c_nf_per_km'],
                max_i_ka=line['max_i_ka'],
                parallel=int(line['parallel']),
                name=line['name']
            )
            
            # Store additional info for visualization
            self.net.line.at[line_idx, 'cables_per_phase'] = line.get('parallel_cables_per_phase', 1)
            
            # Store geographic coordinates if available
            if pd.notna(line.get('geographic_coordinates')):
                self.net.line.at[line_idx, 'geo_coords'] = str(line['geographic_coordinates'])
            
    def _add_transformers(self):
        """Add all transformers"""
        for _, trafo in self.transformers.iterrows():
            hv_bus = self.bus_mapping.get(trafo['hv_bus_id'])
            lv_bus = self.bus_mapping.get(trafo['lv_bus_id'])
            
            if hv_bus is None or lv_bus is None:
                continue
                
            hv_vn = self.net.bus.at[hv_bus, 'vn_kv']
            lv_vn = self.net.bus.at[lv_bus, 'vn_kv']
            
            pp.create_transformer_from_parameters(
                self.net,
                hv_bus=hv_bus,
                lv_bus=lv_bus,
                sn_mva=trafo['sn_mva'],
                vn_hv_kv=hv_vn,
                vn_lv_kv=lv_vn,
                vk_percent=trafo['vk_percent'],
                vkr_percent=trafo['vkr_percent'],
                pfe_kw=trafo['pfe_kw'],
                i0_percent=trafo['i0_percent'],
                name=trafo['transformer_id']
            )
            
    def _add_generators(self):
        """Add generators with configurable PV/PQ control strategy"""
        ext_grid_buses = set(self.net.ext_grid['bus'].values)
        strategy = config.PV_CONTROL_STRATEGY
        
        print(f"\nApplying PV/PQ control strategy: {strategy}")
        
        if strategy == 'voltage_based':
            pv_buses = self._select_pv_buses_voltage_based(ext_grid_buses)
        elif strategy == 'mixed':
            pv_buses = self._select_pv_buses_mixed(ext_grid_buses)
        else:
            raise ValueError(f"Unknown PV control strategy: {strategy}")
        
        # Add generators
        pv_count = 0
        pq_count = 0
        
        for _, gen in self.generators.iterrows():
            bus_idx = self.bus_mapping.get(gen['bus_id'])
            if bus_idx is None:
                continue
            
            # Check if marked as PQ (from voltage level filtering)
            is_pq = gen.get('control_type') == 'PQ'
            
            if bus_idx in pv_buses and not is_pq:
                # PV control
                pp.create_gen(
                    self.net,
                    bus=bus_idx,
                    p_mw=gen['p_mw'],
                    vm_pu=gen['vm_pu'],
                    sn_mva=gen['sn_mva'],
                    name=gen['generator_name'],
                    type=gen['generation_type']
                )
                pv_count += 1
            else:
                # PQ control
                pp.create_sgen(
                    self.net,
                    bus=bus_idx,
                    p_mw=gen['p_mw'],
                    q_mvar=0,
                    sn_mva=gen['sn_mva'],
                    name=gen['generator_name'],
                    type=gen['generation_type']
                )
                pq_count += 1
        
        print(f"  PV generators: {pv_count}")
        print(f"  PQ generators: {pq_count}")
        print(f"  PV/Total ratio: {pv_count/(pv_count+pq_count):.2%}")
                
    def _select_pv_buses_voltage_based(self, ext_grid_buses):
        """Strategy 1: PV control only for specific voltage levels (excluding ext_grid buses)"""
        pv_voltage_levels = config.PV_VOLTAGE_LEVELS
        pv_buses = set()
        
        for _, gen in self.generators.iterrows():
            bus_idx = self.bus_mapping.get(gen['bus_id'])
            if bus_idx is None or bus_idx in ext_grid_buses:
                continue
            
            bus_voltage = self.net.bus.at[bus_idx, 'vn_kv']
            if bus_voltage in pv_voltage_levels:
                pv_buses.add(bus_idx)
        
        return pv_buses
    
    def _select_pv_buses_mixed(self, ext_grid_buses):
        """Strategy 2: Primary voltage level + ratio of secondary voltage level"""
        primary_voltage = config.MIXED_PV_PRIMARY_VOLTAGE
        secondary_voltage = config.MIXED_PV_SECONDARY_VOLTAGE
        secondary_ratio = config.MIXED_PV_SECONDARY_RATIO
        selection_method = config.MIXED_PV_SELECTION_METHOD
        
        pv_buses = set()
        
        # Add all primary voltage generators
        for _, gen in self.generators.iterrows():
            bus_idx = self.bus_mapping.get(gen['bus_id'])
            if bus_idx is None or bus_idx in ext_grid_buses:
                continue
            
            bus_voltage = self.net.bus.at[bus_idx, 'vn_kv']
            if bus_voltage == primary_voltage:
                pv_buses.add(bus_idx)
        
        # Select portion of secondary voltage generators
        secondary_gens = []
        for _, gen in self.generators.iterrows():
            bus_idx = self.bus_mapping.get(gen['bus_id'])
            if bus_idx is None or bus_idx in ext_grid_buses:
                continue
            
            bus_voltage = self.net.bus.at[bus_idx, 'vn_kv']
            if bus_voltage == secondary_voltage:
                secondary_gens.append({
                    'bus_idx': bus_idx,
                    'p_mw': gen['p_mw'],
                    'sn_mva': gen['sn_mva']
                })
        
        # Select secondary PV buses
        n_secondary_pv = int(len(secondary_gens) * secondary_ratio)
        
        if n_secondary_pv > 0 and len(secondary_gens) > 0:
            if selection_method == 'largest':
                # Select largest capacity generators
                secondary_gens.sort(key=lambda x: x['sn_mva'], reverse=True)
                for gen in secondary_gens[:n_secondary_pv]:
                    pv_buses.add(gen['bus_idx'])
            elif selection_method == 'distributed':
                # Select evenly distributed
                step = len(secondary_gens) / n_secondary_pv
                for i in range(n_secondary_pv):
                    idx = int(i * step)
                    pv_buses.add(secondary_gens[idx]['bus_idx'])
        
        return pv_buses
            
    def _add_loads(self):
        """Add all loads"""
        for _, load in self.loads.iterrows():
            bus_idx = self.bus_mapping.get(load['bus_id'])
            if bus_idx is None:
                continue
                
            pp.create_load(
                self.net,
                bus=bus_idx,
                p_mw=load['p_mw'],
                q_mvar=load['q_mvar'],
                name=load['load_name']
            )