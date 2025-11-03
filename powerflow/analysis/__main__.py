"""
Main program - orchestrates the power flow calculation workflow
"""
import sys
from .data_loader import DataLoader
from .data_preprocessor import DataPreprocessor
from .external_grid_manager import ExternalGridManager
from .incremental_network_builder import IncrementalNetworkBuilder
from .power_flow_solver import PowerFlowSolver
from .network_analyzer import NetworkAnalyzer
from .results_exporter import ResultsExporter
from .visualizer import Visualizer

def main():
    """Main workflow"""
    print("\n" + "="*80)
    print("GERMAN GRID POWER FLOW CALCULATION")
    print("="*80 + "\n")

    try:
        # Step 1: Load and preprocess data
        print("[1/6] Loading and preprocessing data...")
        data_loader = DataLoader()
        data_loader.load_all()

        preprocessor = DataPreprocessor(data_loader)
        preprocessor.preprocess_all()

        # Step 2: Setup external grids
        print("\n[2/6] Setting up external grids...")
        ext_grid_manager = ExternalGridManager(
            preprocessor.buses,
            preprocessor.connections,
            data_loader.external_grids
        )
        external_grids = ext_grid_manager.setup_external_grids()

        # Step 3: Build network
        print("\n[3/6] Building network (380kV + 220kV)...")
        inc_builder = IncrementalNetworkBuilder(preprocessor, external_grids)
        net = inc_builder.build_with_incremental_220kv()

        if net is None:
            print("\n✗ Network building failed")
            sys.exit(1)

        # Step 4: Validate and clean network
        print("\n[4/6] Validating and cleaning network...")
        from .network_validity_checker import NetworkValidityChecker
        from .network_cleaner import NetworkCleaner

        checker = NetworkValidityChecker(net)
        is_valid, summary = checker.check_and_clean()

        cleaner = NetworkCleaner(net)
        net = cleaner.clean_isolated_networks()
        net = cleaner.fix_transformers()

        print(f"  ✓ Network validated: {len(net.bus)} buses, {len(net.line)} lines")

        # Step 5: Run power flow
        print("\n[5/6] Running power flow calculation...")
        solver = PowerFlowSolver(net, silent=True)
        converged = solver.solve()

        if not converged:
            print("  ✗ Power flow failed to converge")
            sys.exit(1)

        print("  ✓ Power flow converged")

        # Step 6: Export and visualize
        print("\n[6/6] Exporting results and creating visualization...")
        exporter = ResultsExporter(net)
        exporter.export_all()

        try:
            visualizer = Visualizer(net)
            visualizer.create_map()
            print("  ✓ Visualization created")
        except Exception as e:
            print(f"  ⚠ Visualization failed: {e}")

        # Print final summary
        print_final_summary(net)

    except FileNotFoundError as e:
        print(f"\n✗ Error: Required data file not found - {e}")
        sys.exit(1)

    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def print_final_summary(net):
    """Print concise final summary with key results"""
    print("\n" + "="*80)
    print("POWER FLOW RESULTS")
    print("="*80)

    # Network statistics
    print("\n📊 NETWORK STATISTICS:")
    print(f"   Buses:        {len(net.bus)}")
    print(f"   Lines:        {len(net.line)}")
    print(f"   Transformers: {len(net.trafo)}")
    print(f"   Generators:   {len(net.gen)} PV + {len(net.sgen)} PQ")
    print(f"   Loads:        {len(net.load)}")

    # Power balance
    total_gen = 0
    if len(net.res_gen) > 0:
        total_gen += net.res_gen['p_mw'].sum()
    if len(net.res_sgen) > 0:
        total_gen += net.res_sgen['p_mw'].sum()

    total_load = net.res_load['p_mw'].sum()

    line_losses = net.res_line['pl_mw'].sum() if len(net.res_line) > 0 else 0
    trafo_losses = net.res_trafo['pl_mw'].sum() if len(net.res_trafo) > 0 else 0
    total_losses = line_losses + trafo_losses

    print("\n⚡ POWER BALANCE:")
    print(f"   Generation:   {total_gen:>8.1f} MW")
    print(f"   Load:         {total_load:>8.1f} MW")
    print(f"   Losses:       {total_losses:>8.1f} MW ({total_losses/total_load*100:.2f}%)")

    # Voltage statistics
    v_min = net.res_bus['vm_pu'].min()
    v_max = net.res_bus['vm_pu'].max()
    v_mean = net.res_bus['vm_pu'].mean()

    low_voltage = len(net.res_bus[net.res_bus['vm_pu'] < 0.95])
    high_voltage = len(net.res_bus[net.res_bus['vm_pu'] > 1.05])

    print("\n🔌 VOLTAGE PROFILE:")
    print(f"   Range:        {v_min:.4f} - {v_max:.4f} pu")
    print(f"   Mean:         {v_mean:.4f} pu")
    if low_voltage > 0:
        print(f"   ⚠ Low (<0.95):  {low_voltage} buses")
    if high_voltage > 0:
        print(f"   ⚠ High (>1.05): {high_voltage} buses")

    # Loading statistics
    if len(net.res_line) > 0:
        max_loading = net.res_line['loading_percent'].max()
        overloaded = (net.res_line['loading_percent'] > 100).sum()

        print("\n📈 LINE LOADING:")
        print(f"   Max loading:  {max_loading:.1f}%")
        if overloaded > 0:
            print(f"   ⚠ Overloaded:   {overloaded} lines")

    # Transformer loading
    if len(net.trafo) > 0 and len(net.res_trafo) > 0:
        max_trafo_loading = net.res_trafo['loading_percent'].max()
        trafo_overloaded = (net.res_trafo['loading_percent'] > 100).sum()

        print("\n🔄 TRANSFORMER LOADING:")
        print(f"   Max loading:  {max_trafo_loading:.1f}%")
        if trafo_overloaded > 0:
            print(f"   ⚠ Overloaded:   {trafo_overloaded} transformers")

    # Cross-border power exchange
    print("\n🌍 CROSS-BORDER POWER EXCHANGE:")

    if len(net.res_ext_grid) > 0:
        # Group by country
        ext_grid_power = {}
        for idx, ext_grid in net.ext_grid.iterrows():
            name = ext_grid['name']
            power = net.res_ext_grid.at[idx, 'p_mw']

            # Extract country from name
            country = 'Unknown'
            if 'ExtGrid_' in name:
                country = name.replace('ExtGrid_', '')

            if country not in ext_grid_power:
                ext_grid_power[country] = 0
            ext_grid_power[country] += power

        # Sort by absolute power
        sorted_countries = sorted(ext_grid_power.items(), key=lambda x: abs(x[1]), reverse=True)

        total_import = sum(p for c, p in sorted_countries if p > 0)
        total_export = sum(abs(p) for c, p in sorted_countries if p < 0)

        for country, power in sorted_countries:
            direction = "Import" if power > 0 else "Export"
            symbol = "←" if power > 0 else "→"
            print(f"   {country:<15} {symbol} {abs(power):>8.1f} MW ({direction})")

        print(f"\n   Total Import:  {total_import:>8.1f} MW")
        print(f"   Total Export:  {total_export:>8.1f} MW")
        print(f"   Net Exchange:  {total_import - total_export:>8.1f} MW")

    print("\n" + "="*80)
    print("✓ Results saved to 'results/' directory")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
