"""
Network Analyzer - Post-convergence analysis and non-convergence diagnostics
"""
from . import config

class NetworkAnalyzer:
    def __init__(self, net):
        self.net = net

    def analyze_network_issues(self):
        """Analyze voltage violations, line overloads, and transformer overloads"""
        print("\n" + "="*60)
        print("NETWORK ISSUE ANALYSIS (Post-Convergence)")
        print("="*60)

        self._analyze_voltage_issues()
        self._analyze_line_overloads()
        self._analyze_transformer_overloads()

        print("="*60 + "\n")

    def diagnose_non_convergence(self):
        """Diagnose why power flow failed to converge"""
        print("\n" + "="*60)
        print("NON-CONVERGENCE DIAGNOSTICS")
        print("="*60)

        # 1. Power balance
        print("\n1. POWER BALANCE:")
        total_gen = 0
        if len(self.net.gen) > 0:
            total_gen += self.net.gen['p_mw'].sum()
        if len(self.net.sgen) > 0:
            total_gen += self.net.sgen['p_mw'].sum()

        total_load = self.net.load['p_mw'].sum()
        balance_ratio = total_gen / total_load if total_load > 0 else 0

        print(f"   Generation: {total_gen:.1f} MW")
        print(f"   Load:       {total_load:.1f} MW")
        print(f"   Ratio:      {balance_ratio:.3f}")

        if balance_ratio < 0.90:
            print(f"   ⚠ Generation significantly below load")
        elif balance_ratio > 1.20:
            print(f"   ⚠ Generation significantly above load - may cause voltage issues")

        # 2. Network topology
        print("\n2. NETWORK TOPOLOGY:")
        print(f"   Buses:          {len(self.net.bus)}")
        print(f"   Lines:          {len(self.net.line)}")
        print(f"   Transformers:   {len(self.net.trafo)}")
        print(f"   Voltage levels: {sorted(self.net.bus['vn_kv'].unique())}")

        # 3. Voltage control elements
        print("\n3. VOLTAGE CONTROL:")
        print(f"   External grids: {len(self.net.ext_grid)}")
        print(f"   PV generators:  {len(self.net.gen)}")
        print(f"   PQ generators:  {len(self.net.sgen)}")

        if len(self.net.gen) > 0:
            pv_ratio = len(self.net.gen) / len(self.net.bus)
            print(f"   PV/Bus ratio:   {pv_ratio:.3f}")

            if pv_ratio > 0.25:
                print(f"   ⚠ High PV generator density - may cause voltage control conflicts")

        print("\n" + "="*60)
        print("Suggestion: Check config.py settings (scaling factors, PV strategy)")
        print("="*60 + "\n")

    def _analyze_voltage_issues(self):
        """Analyze voltage violations with table format"""
        print("\n1. VOLTAGE ANALYSIS:")

        v_min = self.net.res_bus['vm_pu'].min()
        v_max = self.net.res_bus['vm_pu'].max()

        print(f"   Range: {v_min:.4f} - {v_max:.4f} pu")

        # Find violations
        low_voltage = self.net.res_bus[self.net.res_bus['vm_pu'] < 0.95]
        high_voltage = self.net.res_bus[self.net.res_bus['vm_pu'] > 1.05]

        if len(low_voltage) > 0:
            print(f"\n   ⚠ LOW VOLTAGE: {len(low_voltage)} buses < 0.95 pu")
            print(f"\n   Top 10 worst cases:")
            print(f"   {'Bus Name':<40} {'Voltage':<12} {'Nominal':<10}")
            print(f"   {'-'*62}")

            worst_low = low_voltage.nsmallest(10, 'vm_pu')
            for idx, row in worst_low.iterrows():
                bus_name = self.net.bus.at[idx, 'name'][:38]
                bus_v = self.net.bus.at[idx, 'vn_kv']
                print(f"   {bus_name:<40} {row['vm_pu']:>6.4f} pu   {bus_v:>4.0f} kV")

        if len(high_voltage) > 0:
            print(f"\n   ⚠ HIGH VOLTAGE: {len(high_voltage)} buses > 1.05 pu")
            print(f"\n   Top 10 worst cases:")
            print(f"   {'Bus Name':<40} {'Voltage':<12} {'Nominal':<10}")
            print(f"   {'-'*62}")

            worst_high = high_voltage.nlargest(10, 'vm_pu')
            for idx, row in worst_high.iterrows():
                bus_name = self.net.bus.at[idx, 'name'][:38]
                bus_v = self.net.bus.at[idx, 'vn_kv']
                print(f"   {bus_name:<40} {row['vm_pu']:>6.4f} pu   {bus_v:>4.0f} kV")

        if len(low_voltage) == 0 and len(high_voltage) == 0:
            print(f"   ✓ All bus voltages within limits (0.95 - 1.05 pu)")

        # By voltage level
        print(f"\n   Voltage statistics by level:")
        print(f"   {'Level':<8} {'Min (pu)':<12} {'Max (pu)':<12} {'Mean (pu)':<12}")
        print(f"   {'-'*44}")

        for vn in sorted(self.net.bus['vn_kv'].unique()):
            buses_at_vn = self.net.bus[self.net.bus['vn_kv'] == vn].index
            v_at_vn = self.net.res_bus.loc[buses_at_vn, 'vm_pu']
            print(f"   {vn:>4.0f} kV  {v_at_vn.min():>8.4f}     {v_at_vn.max():>8.4f}     {v_at_vn.mean():>8.4f}")

    def _analyze_line_overloads(self):
        """Analyze line overloads with table format"""
        print("\n2. LINE OVERLOAD ANALYSIS:")

        if len(self.net.res_line) == 0:
            print("   No lines to analyze")
            return

        overloaded = self.net.res_line[self.net.res_line['loading_percent'] > 100]

        if len(overloaded) == 0:
            print("   ✓ No overloaded lines")
            return

        print(f"   ⚠ {len(overloaded)} lines overloaded (> 100%)")
        print(f"\n   Top 10 overloaded lines:")
        print(f"   {'Line Name':<40} {'Loading':<10} {'Current':<15}")
        print(f"   {'-'*65}")

        worst = overloaded.nlargest(10, 'loading_percent')
        for idx, row in worst.iterrows():
            line_name = self.net.line.at[idx, 'name'][:38]
            current_str = f"{row['i_from_ka']:.2f}/{self.net.line.at[idx, 'max_i_ka']:.2f} kA"
            print(f"   {line_name:<40} {row['loading_percent']:>6.1f} %   {current_str:<15}")

    def _analyze_transformer_overloads(self):
        """Analyze transformer overloads"""
        print("\n3. TRANSFORMER OVERLOAD ANALYSIS:")

        if len(self.net.trafo) == 0 or len(self.net.res_trafo) == 0:
            print("   No transformers to analyze")
            return

        overloaded = self.net.res_trafo[self.net.res_trafo['loading_percent'] > 100]

        if len(overloaded) == 0:
            print("   ✓ No overloaded transformers")
            return

        print(f"   ⚠ {len(overloaded)} transformers overloaded (> 100%)")
        print(f"\n   Top 10 overloaded transformers:")
        print(f"   {'Transformer Name':<40} {'Loading':<10} {'Rating':<10}")
        print(f"   {'-'*60}")

        worst = overloaded.nlargest(10, 'loading_percent')
        for idx, row in worst.iterrows():
            trafo_name = self.net.trafo.at[idx, 'name'][:38]
            rating = f"{self.net.trafo.at[idx, 'sn_mva']:.0f} MVA"
            print(f"   {trafo_name:<40} {row['loading_percent']:>6.1f} %   {rating:<10}")
