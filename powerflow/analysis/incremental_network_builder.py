"""
Incremental network builder
Strategy: 380kV all + 220kV all (no BFS)
"""
import pandas as pd
import pandapower as pp
from . import config

class IncrementalNetworkBuilder:
    def __init__(self, preprocessor, external_grids):
        self.all_buses = preprocessor.buses
        self.all_connections = preprocessor.connections
        self.all_generators = preprocessor.generators
        self.all_loads = preprocessor.loads
        self.all_transformers = preprocessor.transformers
        self.external_grids = external_grids

        # Separate by voltage
        self.buses_380 = self.all_buses[self.all_buses['vn_kv'] == 380].copy()
        self.buses_220 = self.all_buses[self.all_buses['vn_kv'] == 220].copy()

    def build_with_incremental_220kv(self):
        """Build network: 380kV all + 220kV all"""
        print("\n" + "="*80)
        print("NETWORK BUILDING - （380+220）kV")
        print("="*80)

        # Step 1: Build 380kV backbone
        print("\n[Step 1] Building 380kV network...")
        net_current, bus_mapping = self._build_380kv_base()

        from .power_flow_solver import PowerFlowSolver
        solver = PowerFlowSolver(net_current, silent=True)
        if not solver.solve():
            print("  ✗ 380kV network doesn't converge!")
            return None

        print(f"  ✓ 380kV converged: {len(net_current.bus)} buses")

        # Step 2: Add ALL 220kV network
        print(f"\n[Step 2] Adding ALL 220kV network...")
        all_220_ids = list(self.buses_220['bus_id'].values)
        print(f"  Adding {len(all_220_ids)} buses...")

        net_final = self._add_buses_to_network(net_current, bus_mapping, all_220_ids)

        solver = PowerFlowSolver(net_final, silent=True)
        if solver.solve():
            print(f"  ✓ Full network converged: {len(net_final.bus)} buses")
        else:
            print(f"  ✗ Full network failed to converge")
            return None

        print("="*80 + "\n")

        return net_final

    def _build_380kv_base(self):
        """Build initial 380kV network and return with bus mapping"""
        from .network_builder import NetworkBuilder

        class TempPreprocessor:
            pass

        temp = TempPreprocessor()
        temp.buses = self.buses_380
        temp.connections = self.all_connections[
            self.all_connections['from_bus_id'].isin(self.buses_380['bus_id']) &
            self.all_connections['to_bus_id'].isin(self.buses_380['bus_id'])
        ]
        temp.generators = self.all_generators[
            self.all_generators['bus_id'].isin(self.buses_380['bus_id'])
        ]
        temp.loads = self.all_loads[
            self.all_loads['bus_id'].isin(self.buses_380['bus_id'])
        ]
        temp.transformers = pd.DataFrame(columns=self.all_transformers.columns)

        # Filter external grids
        external_grids_380 = [
            eg for eg in self.external_grids
            if eg['bus_id'] in self.buses_380['bus_id'].values
        ]

        print(f"   Using {len(external_grids_380)} external grids (380kV only)")

        builder = NetworkBuilder(temp, external_grids_380)
        net = builder.build_network()

        # Build bus mapping
        bus_mapping = {}
        for idx, row in net.bus.iterrows():
            matches = self.buses_380[
                (self.buses_380['name'] == row['name']) &
                (self.buses_380['vn_kv'] == row['vn_kv'])
            ]
            if len(matches) > 0:
                bus_mapping[matches.iloc[0]['bus_id']] = idx

        return net, bus_mapping

    def _add_buses_to_network(self, base_net, bus_mapping, new_bus_ids):
        """Add a list of buses and their connections to network"""
        import copy
        net = copy.deepcopy(base_net)

        # Update bus_mapping with new buses
        for bus_id in new_bus_ids:
            if bus_id in bus_mapping:
                continue

            bus_row = self.buses_220[self.buses_220['bus_id'] == bus_id].iloc[0]

            idx = pp.create_bus(
                net,
                vn_kv=bus_row['vn_kv'],
                name=bus_row['name'],
                geodata=(bus_row['lat'], bus_row['lon'])
            )
            net.bus.at[idx, 'geo'] = (bus_row['lat'], bus_row['lon'])
            bus_mapping[bus_id] = idx

        # Add transformers
        for _, trafo in self.all_transformers.iterrows():
            hv_id = trafo['hv_bus_id']
            lv_id = trafo['lv_bus_id']

            if hv_id in bus_mapping and lv_id in bus_mapping:
                hv_idx = bus_mapping[hv_id]
                lv_idx = bus_mapping[lv_id]

                existing = net.trafo[
                    (net.trafo['hv_bus'] == hv_idx) &
                    (net.trafo['lv_bus'] == lv_idx)
                ]

                if len(existing) == 0:
                    pp.create_transformer_from_parameters(
                        net,
                        hv_bus=hv_idx,
                        lv_bus=lv_idx,
                        sn_mva=trafo['sn_mva'],
                        vn_hv_kv=net.bus.at[hv_idx, 'vn_kv'],
                        vn_lv_kv=net.bus.at[lv_idx, 'vn_kv'],
                        vk_percent=trafo['vk_percent'],
                        vkr_percent=trafo['vkr_percent'],
                        pfe_kw=trafo['pfe_kw'],
                        i0_percent=trafo['i0_percent'],
                        name=trafo['transformer_id']
                    )

        # Add lines
        for _, line in self.all_connections.iterrows():
            from_id = line['from_bus_id']
            to_id = line['to_bus_id']

            if from_id in bus_mapping and to_id in bus_mapping:
                from_idx = bus_mapping[from_id]
                to_idx = bus_mapping[to_id]

                existing = net.line[
                    ((net.line['from_bus'] == from_idx) & (net.line['to_bus'] == to_idx)) |
                    ((net.line['from_bus'] == to_idx) & (net.line['to_bus'] == from_idx))
                ]

                if len(existing) == 0:
                    line_idx = pp.create_line_from_parameters(
                        net,
                        from_bus=from_idx,
                        to_bus=to_idx,
                        length_km=line['length_km'],
                        r_ohm_per_km=line['r_ohm_per_km'],
                        x_ohm_per_km=line['x_ohm_per_km'],
                        c_nf_per_km=line['c_nf_per_km'],
                        max_i_ka=line['max_i_ka'],
                        parallel=int(line['parallel']),
                        name=line['name']
                    )
                    net.line.at[line_idx, 'cables_per_phase'] = line.get('parallel_cables_per_phase', 1)

                    if pd.notna(line.get('geographic_coordinates')):
                        net.line.at[line_idx, 'geo_coords'] = str(line['geographic_coordinates'])

        # Add generators
        for _, gen in self.all_generators.iterrows():
            if gen['bus_id'] in new_bus_ids and gen['bus_id'] in bus_mapping:
                bus_idx = bus_mapping[gen['bus_id']]

                pp.create_sgen(
                    net,
                    bus=bus_idx,
                    p_mw=gen['p_mw'],
                    q_mvar=0,
                    sn_mva=gen['sn_mva'],
                    name=gen['generator_name'],
                    type=gen['generation_type']
                )

        # Add loads
        for _, load in self.all_loads.iterrows():
            if load['bus_id'] in new_bus_ids and load['bus_id'] in bus_mapping:
                bus_idx = bus_mapping[load['bus_id']]

                pp.create_load(
                    net,
                    bus=bus_idx,
                    p_mw=load['p_mw'],
                    q_mvar=load['q_mvar'],
                    name=load['load_name']
                )

        return net
