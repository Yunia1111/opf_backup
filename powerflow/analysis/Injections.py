"""
Injections- Calculates the maximum injection capacity.
Warm Start, Cost Reset, Map Generation.
"""
import copy
import numpy as np
import pandas as pd
import pandapower as pp
from . import config
from .opf import OPFEngine
from . import report_export as ReportGenerator
from . import visualization as Visualizer

class InjectionAnalyzer:
    def __init__(self, base_net, external_grids):
        self.base_net = base_net
        self.external_grids = external_grids
        self.engine_helper = OPFEngine(base_net, external_grids)

    def find_best_connection_point(self, lat, lon, min_vn_kv=110.0):
        print(f"  > Searching for nearest bus to ({lat}, {lon}) with Voltage >= {min_vn_kv}kV...")
        suitable_buses = self.base_net.bus[self.base_net.bus['vn_kv'] >= min_vn_kv].copy()

        def calc_dist(row):
            bus_geo = self.base_net.bus.at[row.name, 'geo']
            return (lat - bus_geo[0])**2 + (lon - bus_geo[1])**2 if bus_geo else float('inf')

        suitable_buses['dist_sq'] = suitable_buses.apply(calc_dist, axis=1)
        nearest = suitable_buses.loc[suitable_buses['dist_sq'].idxmin()]
        dist_km = np.sqrt(nearest['dist_sq']) * 111.0

        print(f"    Found Bus {nearest.name} ('{nearest['name']}') {nearest['vn_kv']} kV, ~{dist_km:.2f} km")
        return nearest.name, nearest['vn_kv'], dist_km

    def analyze_hosting_capacity(self, lat, lon, scenario_name='average_of_2024', base_result_net=None):
        bus_idx, vn_kv, dist = self.find_best_connection_point(lat, lon)
        print(f"\n[Injection Analysis] Assessing capacity at Bus {bus_idx}...")

        # 1. 准备网络
        if base_result_net:
            print("  > Using Warm Start.")
            net = copy.deepcopy(base_result_net)
        else:
            print("  > Cold Start.")
            scen = self.engine_helper.scenarios[scenario_name]
            net, _ = self.engine_helper._apply_scenario(scen)

            # [CRITICAL FIX]
            # If cold start, we have no results yet. Smart Constraint Filtering relies on
            # knowing which lines are currently overloaded. We must run a basic PF first.
            print("  > Running pre-calc Power Flow for constraint filtering...")
            try:
                pp.runpp(net, numba=False)
            except Exception as e:
                print(f"    Warning: Pre-calc PF failed ({e}). Filtering might be less effective.")

        # 2. 添加虚拟发电机
        inj_idx = pp.create_gen(net, bus=bus_idx, p_mw=0, min_p_mw=0, max_p_mw=5000,
            vm_pu=1.02, sn_mva=5000, name="VIRTUAL_INJECTION_TEST", type="virtual_injection", controllable=True)

        # 3. 设置基础成本
        if 'poly_cost' in net: net.poly_cost.drop(net.poly_cost.index, inplace=True)
        self.engine_helper.scenario_net = net
        self.engine_helper._setup_opf_costs()

        # 4. 设置注入负成本 (激励注入)
        cost_df = net.poly_cost
        v_idx = cost_df[(cost_df['et']=='gen') & (cost_df['element']==inj_idx)].index
        if len(v_idx) > 0:
            net.poly_cost.at[v_idx[0], 'cp1_eur_per_mw'] = -1000.0
            if 'cp2_eur_per_mw2' in net.poly_cost.columns: net.poly_cost.at[v_idx[0], 'cp2_eur_per_mw2'] = 0.0
        else:
            pp.create_poly_cost(net, element=inj_idx, et='gen', cp1_eur_per_mw=-1000.0)

        # =================================================================
        # [NEW] 智能约束筛选 (Smart Constraint Filtering)
        # =================================================================
        TARGET_LIMIT = config.MAX_LINE_LOADING_PERCENT if config.MAX_LINE_LOADING_PERCENT > 0 else 100.0

        print(f"  > Applying smart line limits (Target: {TARGET_LIMIT}%)...")

        # Reset limits
        net.line['max_loading_percent'] = 0.0

        # Identify critical lines
        if 'loading_percent' in net.res_line.columns:
            critical_mask = net.res_line['loading_percent'] > 80.0
            critical_lines = net.res_line[critical_mask].index
        else:
            critical_lines = []

        connected_lines = net.line[(net.line.from_bus == bus_idx) | (net.line.to_bus == bus_idx)].index
        all_constrained_lines = set(critical_lines).union(set(connected_lines))

        for line_id in all_constrained_lines:
            # Check for existing loading to avoid immediate infeasibility
            current_load = 0
            if 'loading_percent' in net.res_line.columns and line_id in net.res_line.index:
                current_load = net.res_line.at[line_id, 'loading_percent']

            safe_limit = max(TARGET_LIMIT, current_load + 20.0)
            net.line.at[line_id, 'max_loading_percent'] = safe_limit

        print(f"    - Enforced limits on {len(all_constrained_lines)} critical lines.")
        # =================================================================

        print("  > Optimizing...")
        converged = self.engine_helper._solve_opf()

        if not converged:
            print("  ✗ Optimization failed.")
            return None

        mw = net.res_gen.at[inj_idx, 'p_mw']
        limit = self._identify_limit(net)
        res = {'location': (lat, lon), 'bus_id': bus_idx, 'bus_name': net.bus.at[bus_idx, 'name'],
               'bus_voltage': vn_kv, 'max_injection_mw': mw, 'limiting_factor': limit,
               'battery_suggestion': f"{mw*0.5:.1f} MW / {mw*2:.1f} MWh", 'scenario_used': scenario_name}

        self._print_report(res)

        print("  > Generating Map...")
        exporter = ReportGenerator.ReportGenerator(net)
        exporter.export_all("injection_result")
        Visualizer.Visualizer().create_map(net, {'name': "injection_result", 'description': f"Injection at {lat},{lon}"})
        return res

    def _identify_limit(self, net):
        # Improved Limit Detection
        if len(net.res_line) > 0:
            load = net.res_line['loading_percent'].max()
            if load >= (config.MAX_LINE_LOADING_PERCENT - 2.0):
                return f"Line Overload ({load:.1f}%)"

        inj_gen = net.gen[net.gen['type'] == 'virtual_injection']
        if not inj_gen.empty:
            idx = inj_gen.index[0]
            if net.res_gen.at[idx, 'p_mw'] >= 4990: # Near 5000 max
                return "Upper Bound (5000 MW)"

        return "Voltage/Convergence"

    def _print_report(self, res):
        print(f"\n📍 MAX CAPACITY: {res['max_injection_mw']:,.2f} MW")
        print(f"🛑 Limit: {res['limiting_factor']}\n")
