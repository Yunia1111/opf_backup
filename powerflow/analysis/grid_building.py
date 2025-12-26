"""
Grid building - load, preprocess, and construct the static
pandapower base network (net_0) with nameplate capacities.
"""
import pandas as pd
import numpy as np
import pandapower as pp
import pandapower.topology as top
import networkx as nx
import os
import pickle
import json
from . import config

class GridModeler:

    def __init__(self):
        self.buses = None
        self.connections = None
        self.generators = None
        self.loads = None
        self.transformers = None
        self.external_grids = None
        self.base_net = None
        self.bus_mapping = {}
        self.ext_grid_list = []

    def create_base_network(self):
        cache_path = os.path.join(config.OUTPUT_DIR, config.NETWORK_CACHE_FILE)
        disc_cache_path = os.path.join(config.OUTPUT_DIR, "disconnected_buses.json")

        # 1. Check if we can load from cache
        if not config.FORCE_NETWORK_REBUILD and os.path.exists(cache_path):
            print(f"1. Loading base network from cache: {cache_path}")
            try:
                with open(cache_path, 'rb') as f:
                    self.base_net, self.ext_grid_list = pickle.load(f)
                print(f"  ✓ Cache loaded successfully: {len(self.base_net.bus)} buses.")
                return self.base_net, self.ext_grid_list
            except Exception as e:
                print(f"  ⚠ Cache load failed ({e}), falling back to rebuild.")

        print("1. Loading raw data (Rebuilding network)...")
        self._load_data()

        print("2. Preprocessing data (cleaning & merging)...")
        self._preprocess_data()

        print("3. Configuring external grids...")
        self._setup_external_grids()

        print("4. Building pandapower base net (nameplate capacity)...")
        self.base_net = self._build_network_from_components()

        #  Connectivity Check & Disconnected Component Handling 
        print("  > Checking network connectivity...")
        mg = top.create_nxgraph(self.base_net)
        islands = list(nx.connected_components(mg))
        main_island_buses = max(islands, key=len)

        # Identify disconnected buses
        all_buses = set(self.base_net.bus.index)
        connected_buses_set = set(main_island_buses)
        disconnected_indices = list(all_buses - connected_buses_set)

        print(f"  > Found {len(islands)} components. Keeping largest ({len(main_island_buses)} buses).")
        print(f"  > Removing {len(disconnected_indices)} disconnected buses...")

        # Save disconnected buses to JSON for visualization
        if len(disconnected_indices) > 0:
            disc_data = []
            for idx in disconnected_indices:
                bus_row = self.base_net.bus.loc[idx]
                geo = bus_row['geo']
                if geo:
                    disc_data.append({
                        'id': int(idx),
                        'name': str(bus_row['name']),
                        'vn_kv': float(bus_row['vn_kv']),
                        'lat': float(geo[0]),
                        'lon': float(geo[1])
                    })

            os.makedirs(config.OUTPUT_DIR, exist_ok=True)
            with open(disc_cache_path, 'w') as f:
                json.dump(disc_data, f)
            print(f"    (Saved {len(disc_data)} disconnected buses for visualization)")
        else:
            if os.path.exists(disc_cache_path):
                os.remove(disc_cache_path)

        # Remove them from the OPF network
        self.base_net = pp.select_subnet(self.base_net, buses=main_island_buses)

        # === Save to Cache ===
        print(f"  > Saving built network to cache: {cache_path} ...")
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)

        with open(cache_path, 'wb') as f:
            pickle.dump((self.base_net, self.ext_grid_list), f)
        print("  ✓ Network cached.")

        return self.base_net, self.ext_grid_list

    # data loading, remove pst related parts
    def _load_data(self):
        def _load_csv(filename):
            path = os.path.join(config.DATA_DIR, filename)
            if not os.path.exists(path):
                raise FileNotFoundError(f"Required file not found: {path}")
            df = pd.read_csv(path, sep=';')
            return df

        self.buses = _load_csv("buses.csv")
        self.connections = _load_csv("connections.csv")
        self.generators = _load_csv("generators.csv")
        self.loads = _load_csv("loads.csv")
        self.transformers = _load_csv("transformers.csv")

        try:
            self.hvdc_projects = _load_csv("hvdc_projects.csv")
            print(f"  > Found HVDC projects file: {len(self.hvdc_projects)} lines.")
        except FileNotFoundError:
            self.hvdc_projects = None
            print("  > No HVDC projects file found (skipping).")

        try:
            self.external_grids = _load_csv("external_grids.csv")
        except FileNotFoundError:
            self.external_grids = None

    #  Data Preprocessing 
    def _preprocess_data(self):
        pf = config.POWER_FACTOR
        tan_phi = np.tan(np.arccos(pf))
        self.loads['q_mvar'] = self.loads['p_mw'] * tan_phi

        self.generators = self.generators.groupby(
            ['bus_id', 'generation_type'], as_index=False
        ).agg({
            'p_mw': 'sum', 'vm_pu': 'mean', 'sn_mva': 'sum',
            'generator_name': lambda x: f"merged_{x.iloc[0].split('_')[1] if '_' in x.iloc[0] else 'gen'}_{len(x)}units",
            'commissioning_year': 'first'
        })

        self.connections.loc[:, 'parallel_cables_per_phase'] = self.connections['parallel_cables_per_phase'].fillna(1)
        self.connections['r_ohm_per_km'] = self.connections['r_ohm_per_km'] / self.connections['parallel_cables_per_phase']
        self.connections['x_ohm_per_km'] = self.connections['x_ohm_per_km'] / self.connections['parallel_cables_per_phase']
        self.connections['c_nf_per_km'] = self.connections['c_nf_per_km'] * self.connections['parallel_cables_per_phase']
        self.connections['max_i_ka'] = self.connections['max_i_ka'] * self.connections['parallel_cables_per_phase']
        self.connections['parallel'] = 1

        group_cols = ['from_bus_id', 'to_bus_id', 'length_km', 'r_ohm_per_km',
                     'x_ohm_per_km', 'c_nf_per_km', 'max_i_ka', 'line_type', 'ac_dc_type']
        self.connections = self.connections.groupby(group_cols, as_index=False, dropna=False).agg({
            'parallel': 'sum', 'name': 'first', 'geographic_coordinates': 'first',
            'parallel_cables_per_phase': 'first', 'switch_group': 'first',
            'commissioning_year': 'first'
        })

        self.transformers['vk_percent'] = config.TRAFO_VK_PERCENT
        self.transformers['vkr_percent'] = config.TRAFO_VKR_PERCENT
        self.transformers['pfe_kw'] = config.TRAFO_PFE_KW
        self.transformers['i0_percent'] = config.TRAFO_I0_PERCENT

    # --- External Grid Setup ---
    def _setup_external_grids(self):
        if self.external_grids is not None and len(self.external_grids) > 0:
            for _, row in self.external_grids.iterrows():
                bus_id = row['bus_id']
                if bus_id not in self.buses['bus_id'].values:
                    continue

                grid_type = row.get('grid_type', 'border')
                va_degree = 0.0 if grid_type == 'main_slack' else None
                slack_weight = 1.0 if grid_type == 'main_slack' else 0.0

                ext_grid = {
                    'bus_id': bus_id,
                    'vm_pu': row.get('vm_pu', config.DEFAULT_SLACK_VM_PU),
                    'va_degree': va_degree,
                    'max_p_mw': row.get('max_p_mw', 999999),
                    'min_p_mw': row.get('min_p_mw', -999999),
                    'country': row.get('country', 'Unknown'),
                    'type': grid_type,
                    'slack_weight': slack_weight
                }
                self.ext_grid_list.append(ext_grid)
        print(f"  {len(self.ext_grid_list)} external grids configured.")

    # --- Network Building ---
    def _build_network_from_components(self):
        net = pp.create_empty_network(name="German Grid Base")

        target_vns = config.STANDARD_VOLTAGE_LEVELS
        buses_to_add = self.buses[self.buses['vn_kv'].isin(target_vns)].copy()

        # 1. Add Buses
        for _, bus in buses_to_add.iterrows():
            idx = pp.create_bus(
                net, vn_kv=bus['vn_kv'], name=bus['name'], geodata=(bus['lat'], bus['lon'])
            )
            self.bus_mapping[bus['bus_id']] = idx
            net.bus.at[idx, 'geo'] = (bus['lat'], bus['lon'])

        added_bus_pp_indices = set(net.bus.index)
        ext_grid_buses = set()

        # 2. Add External Grids
        for eg in self.ext_grid_list:
            bus_idx = self.bus_mapping.get(eg['bus_id'])
            if bus_idx in added_bus_pp_indices:
                if eg['type'] == 'main_slack':
                    pp.create_ext_grid(
                        net, bus=bus_idx, vm_pu=eg['vm_pu'], va_degree=eg.get('va_degree', 0.0),
                        max_p_mw=eg['max_p_mw'], min_p_mw=eg['min_p_mw'],
                        name=f"ExtGrid_{eg['country']}", slack_weight=eg['slack_weight']
                    )
                    net.ext_grid.at[net.ext_grid.index[-1], 'type'] = 'main_slack'
                    ext_grid_buses.add(bus_idx)
                else:
                    p_limit_max = eg['max_p_mw']
                    p_limit_min = eg['min_p_mw']
                    sn_mva = max(abs(p_limit_max), abs(p_limit_min))
                    if sn_mva == 0: sn_mva = 1000.0

                    pp.create_gen(
                        net, bus=bus_idx, p_mw=0.0, vm_pu=eg['vm_pu'],
                        sn_mva=sn_mva,
                        min_p_mw=p_limit_min, max_p_mw=p_limit_max,
                        name=f"Border_{eg['country']}",
                        type='border',
                        controllable=True
                    )
                    net.gen.at[net.gen.index[-1], 'nameplate_p_mw'] = sn_mva
                    net.gen.at[net.gen.index[-1], 'nameplate_sn_mva'] = sn_mva
                    ext_grid_buses.add(bus_idx)

        # 3. Add Lines
        for _, line in self.connections.iterrows():
            from_bus = self.bus_mapping.get(line['from_bus_id'])
            to_bus = self.bus_mapping.get(line['to_bus_id'])
            if from_bus in added_bus_pp_indices and to_bus in added_bus_pp_indices:
                line_idx = pp.create_line_from_parameters(
                    net, from_bus=from_bus, to_bus=to_bus, length_km=line['length_km'],
                    r_ohm_per_km=line['r_ohm_per_km'], x_ohm_per_km=line['x_ohm_per_km'],
                    c_nf_per_km=line['c_nf_per_km'], max_i_ka=line['max_i_ka'],
                    parallel=int(line['parallel']), name=line['name']
                )
                net.line.at[line_idx, 'cables_per_phase'] = line.get('parallel_cables_per_phase', 1)
                if pd.notna(line.get('geographic_coordinates')):
                    net.line.at[line_idx, 'geo_coords'] = str(line['geographic_coordinates'])

        # 4. Add Transformers
        for _, trafo in self.transformers.iterrows():
            hv_bus = self.bus_mapping.get(trafo['hv_bus_id'])
            lv_bus = self.bus_mapping.get(trafo['lv_bus_id'])
            if hv_bus in added_bus_pp_indices and lv_bus in added_bus_pp_indices:
                hv_vn = net.bus.at[hv_bus, 'vn_kv']
                lv_vn = net.bus.at[lv_bus, 'vn_kv']
                pp.create_transformer_from_parameters(
                    net, hv_bus=hv_bus, lv_bus=lv_bus, sn_mva=trafo['sn_mva'],
                    vn_hv_kv=hv_vn, vn_lv_kv=lv_vn, vk_percent=trafo['vk_percent'],
                    vkr_percent=trafo['vkr_percent'], pfe_kw=trafo['pfe_kw'],
                    i0_percent=trafo['i0_percent'], name=trafo['transformer_id']
                )

        self._add_hvdc_lines(net)
        self._add_generators_and_loads(net, ext_grid_buses)

        return net

    # --- Generators and Loads ---
    def _add_generators_and_loads(self, net, ext_grid_buses):
        pv_buses = self._select_pv_buses_strategy(net, ext_grid_buses)

        for _, gen in self.generators.iterrows():
            bus_idx = self.bus_mapping.get(gen['bus_id'])
            if bus_idx is None or bus_idx not in net.bus.index:
                continue

            nameplate_p = gen['p_mw']
            nameplate_sn = gen['sn_mva']
            gen_type = str(gen['generation_type']).lower()

            if 'storage' in gen_type:
                max_p = nameplate_p
                max_e = nameplate_sn * 2
                pp.create_storage(net, bus=bus_idx, p_mw=0, max_e_mwh=max_e,
                                  max_p_mw=max_p, min_p_mw=-max_p, q_mvar=0,
                                  sn_mva=nameplate_sn, name=gen['generator_name'], type=gen['generation_type'],
                                  controllable=True)
                net.storage.at[net.storage.index[-1], 'nameplate_p_mw'] = max_p
                net.storage.at[net.storage.index[-1], 'nameplate_sn_mva'] = nameplate_sn
                continue

            if bus_idx in pv_buses:
                # PV Node
                pp.create_gen(net, bus=bus_idx, p_mw=nameplate_p, vm_pu=gen['vm_pu'],
                              sn_mva=nameplate_sn, name=gen['generator_name'],
                              type=gen['generation_type'], controllable=True)
                net.gen.at[net.gen.index[-1], 'nameplate_p_mw'] = nameplate_p
                net.gen.at[net.gen.index[-1], 'nameplate_sn_mva'] = nameplate_sn
            else:
                # PQ Node
                pp.create_sgen(net, bus=bus_idx, p_mw=nameplate_p, q_mvar=0,
                               sn_mva=nameplate_sn, name=gen['generator_name'],
                               type=gen['generation_type'], controllable=True)
                net.sgen.at[net.sgen.index[-1], 'nameplate_p_mw'] = nameplate_p
                net.sgen.at[net.sgen.index[-1], 'nameplate_sn_mva'] = nameplate_sn

        for _, load in self.loads.iterrows():
            bus_idx = self.bus_mapping.get(load['bus_id'])
            if bus_idx is not None and bus_idx in net.bus.index:
                p_mw = load['p_mw']
                q_mvar = load['q_mvar']
                pp.create_load(net, bus=bus_idx, p_mw=p_mw, q_mvar=q_mvar, name=load['load_name'])
                net.load.at[net.load.index[-1], 'nameplate_p_mw'] = p_mw
                net.load.at[net.load.index[-1], 'nameplate_q_mvar'] = q_mvar

    def _select_pv_buses_strategy(self, net, ext_grid_buses):
        strategy = config.PV_CONTROL_STRATEGY
        pv_buses = set()

        for _, gen in self.generators.iterrows():
            bus_id = gen['bus_id']
            bus_idx = self.bus_mapping.get(bus_id)
            if bus_idx is None or bus_idx in ext_grid_buses or bus_idx not in net.bus.index:
                continue

            bus_voltage = net.bus.at[bus_idx, 'vn_kv']

            if strategy == 'mixed':
                if bus_voltage in [220.0, 380.0]:
                    pv_buses.add(bus_idx)
            elif strategy == 'voltage_based':
                if bus_voltage in config.PV_VOLTAGE_LEVELS:
                    pv_buses.add(bus_idx)
            elif strategy == 'all_gen_buses':
                pv_buses.add(bus_idx)

        return pv_buses

    # --- HVDC Helpers ---
    def _add_hvdc_lines(self, net):
        if self.hvdc_projects is None or len(self.hvdc_projects) == 0:
            return

        print("  > Integrating HVDC Projects (SuedLink/SuedOstLink)...")
        hv_buses = net.bus[net.bus.vn_kv == 380.0].copy()
        if hv_buses.empty: return

        def find_nearest(lat, lon):
            dists = (hv_buses['geo'].apply(lambda x: x[0]) - lat)**2 + \
                    (hv_buses['geo'].apply(lambda x: x[1]) - lon)**2
            return dists.idxmin()

        count = 0
        for _, row in self.hvdc_projects.iterrows():
            if str(row.get('in_service', 'false')).lower() != 'true': continue
            from_bus = find_nearest(row['from_lat'], row['from_lon'])
            to_bus = find_nearest(row['to_lat'], row['to_lon'])

            pp.create_dcline(net, from_bus=from_bus, to_bus=to_bus, p_mw=row['capacity_mw'],
                loss_percent=1.5, loss_mw=0.5, vm_from_pu=1.0, vm_to_pu=1.0,
                max_p_mw=row['capacity_mw'], min_q_from_mvar=-row['capacity_mw']*0.5,
                max_q_from_mvar=row['capacity_mw']*0.5, min_q_to_mvar=-row['capacity_mw']*0.5,
                max_q_to_mvar=row['capacity_mw']*0.5, name=row['name'], in_service=True, controllable=True)
            count += 1
        print(f"  > Added {count} HVDC corridors.")
