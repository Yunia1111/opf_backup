"""
Main program for multi-scenario optimal power flow calculation.
Controls the workflow: Build Base Net -> Run Scenarios (OPF) -> Summarize -> Injection Analysis.
"""
import sys
import os
import pandas as pd
import time
import config

# Importing modules (RENAMED)
import grid_building
import opf
import report_export
import visualization
import Injections

# Try importing scenarios, handle missing file gracefully
try:
    from scenarios import SCENARIOS # Updated Import
except ImportError:
    print("CRITICAL ERROR: 'scenarios.py' not found.")
    print("Please ensure scenarios.py exists with a dictionary named SCENARIOS.")
    sys.exit(1)

def main():
    print("\n" + "="*80)
    print("GERMAN GRID MULTI-SCENARIO OPF ANALYSIS (V2.1 - Production)")
    print("="*80 + "\n")
    
    # Pre-flight check
    if not os.path.exists(config.DATA_DIR):
        print(f"ERROR: Data directory '{config.DATA_DIR}' not found.")
        sys.exit(1)

    all_results = []
    solved_networks = {} 
    
    try:
        # ==============================================================================
        # STEP 1: BUILD STATIC BASE NETWORK (net_0)
        # ==============================================================================
        print("[STEP 1/2] Building static base network (net_0)...")
        print("─" * 80)
        
        # Updated Class Instantiation
        modeler = grid_building.GridModeler()
        base_net, external_grids = modeler.create_base_network()
        
        total_gen_nameplate = base_net.gen['p_mw'].sum() + base_net.sgen['p_mw'].sum()
        total_load_nameplate = base_net.load['p_mw'].sum()
        print(f"\n  ✓ Base network (net_0) ready: {len(base_net.bus)} buses, "
              f"{len(base_net.line)} lines, {len(base_net.gen)} PV, "
              f"{len(base_net.sgen)} PQ, {len(base_net.storage)} storage")
        print(f"  > Nameplate Capacity: Gen={total_gen_nameplate:,.0f} MW, Load={total_load_nameplate:,.0f} MW")
        
        # Updated Class Instantiation
        opf_engine = opf.OPFEngine(base_net, external_grids)

        # ==============================================================================
        # STEP 2: RUN SCENARIOS (net_1, net_2, ...)
        # ==============================================================================
        print("\n" + "="*80)
        print("[STEP 2/2] Running scenarios with OPF Engine...")
        print("="*80)
        
        # --- SCENARIO SELECTION ---
        # Run ALL scenarios defined in scenarios.py
        scenario_list = list(SCENARIOS.keys()) 
        #scenario_list = ['average_of_2024']
        
        print(f"\nTotal scenarios to run: {len(scenario_list)}")
        print(f"Scenarios: {', '.join(scenario_list)}\n")
        
        for i, scenario_name in enumerate(scenario_list, 1):
            scenario_start_time = time.time()
            
            print("─" * 80)
            print(f"[{i}/{len(scenario_list)}] SCENARIO: {scenario_name.upper()}")
            
            # Run the scenario through the OPF Engine
            scenario_net, scenario_info, converged = opf_engine.run_scenario(scenario_name)
            
            scenario_time = time.time() - scenario_start_time
            
            # Calculate results
            scenario_results = calculate_scenario_results(scenario_net, scenario_info, scenario_time)
            scenario_results['scenario'] = scenario_name
            all_results.append(scenario_results)
            
            # Print intermediate results
            print_scenario_summary(scenario_results)

            if not converged:
                print(f"  ✗ Scenario {scenario_name} FAILED to converge. Skipping export.")
                # We still store non-converged results for comparison, but don't use for injection
                continue

            # Store the solved network for Warm Start
            solved_networks[scenario_name] = scenario_net

            print(f"  ✓ OPF converged ({scenario_time:.1f}s). Exporting results...")
            
            # Updated Class Instantiation
            exporter = report_export.ReportGenerator(scenario_net)
            visualizer = visualization.Visualizer()
            
            exporter.export_all(scenario_name)
            visualizer.create_map(scenario_net, scenario_info)
        
        # ==============================================================================
        # STEP 3: COMPARISON SUMMARY
        # ==============================================================================
        print("\n" + "="*80)
        print("SCENARIO COMPARISON SUMMARY")
        print("="*80 + "\n")
        
        if all_results:
            df_results = pd.DataFrame(all_results)
            print_comparison_table(df_results)
            
            os.makedirs(config.OUTPUT_DIR, exist_ok=True)
            comparison_file = f"{config.OUTPUT_DIR}scenario_comparison.csv"
            df_results.to_csv(comparison_file, index=False, float_format='%.2f')
            print(f"\n✓ Comparison table saved to: {comparison_file}")
        else:
            print("No results to summarize.")

        # ==============================================================================
        # STEP 4: MANUAL INJECTION ANALYSIS (With Warm Start)
        # ==============================================================================
        if config.RUN_INJECTION_ANALYSIS:
            print("\n" + "="*80)
            print("MANUAL INJECTION CAPACITY ANALYSIS")
            print("="*80)
            
            # Updated Class Instantiation
            analyzer = Injections.InjectionAnalyzer(base_net, external_grids)
            
            # --- USER INPUT: Coordinates (Example: Near Munich) ---
            target_lat = 48.13
            target_lon = 11.58
            
            # --- USER INPUT: Background Scenario ---
            # Automatically pick the first successful scenario if 'average_of_2024' isn't available
            INJECTION_SCENARIO = 'average_of_2024'
            if INJECTION_SCENARIO not in solved_networks and len(solved_networks) > 0:
                INJECTION_SCENARIO = list(solved_networks.keys())[0]
                print(f"  ! Default scenario not found, switching to: {INJECTION_SCENARIO}")
            
            base_result_net = None
            
            if INJECTION_SCENARIO in solved_networks:
                print(f"  ★ Warm Start Available: Using pre-calculated results from '{INJECTION_SCENARIO}'")
                base_result_net = solved_networks[INJECTION_SCENARIO]
            else:
                print(f"  ⚠ Warm Start NOT Available for '{INJECTION_SCENARIO}'.")
                print(f"    Running Cold Start...")
            
            analyzer.analyze_hosting_capacity(
                target_lat, target_lon, 
                scenario_name=INJECTION_SCENARIO,
                base_result_net=base_result_net
            )
        else:
            print("\n[INFO] Injection Analysis skipped (RUN_INJECTION_ANALYSIS = False).")
        
    except Exception as e:
        print(f"\n✗ Error during main execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# --- Helper functions ---

def calculate_scenario_results(net, scenario_info, solve_time):
    try:
        gen_p = net.res_gen[net.gen['type'] != 'border']['p_mw'].sum()
        sgen_p = net.res_sgen['p_mw'].sum()
        total_gen_domestic = gen_p + sgen_p
        
        storage_p = net.res_storage['p_mw']
        storage_discharge = storage_p[storage_p > 0].sum()
        storage_charge = abs(storage_p[storage_p < 0].sum())
        
        border_p = net.res_gen[net.gen['type'] == 'border']['p_mw'].sum()
        slack_p = net.res_ext_grid['p_mw'].sum()
        net_import = border_p + slack_p
        
        fixed_load = net.load['p_mw'].sum()
        
        line_losses = net.res_line['pl_mw'].sum() if len(net.res_line) > 0 else 0
        trafo_losses = net.res_trafo['pl_mw'].sum() if len(net.res_trafo) > 0 else 0
        total_losses = line_losses + trafo_losses
        
        v_low = (net.res_bus['vm_pu'] < config.BUS_MIN_VM_PU).sum()
        v_high = (net.res_bus['vm_pu'] > config.BUS_MAX_VM_PU).sum()
        voltage_violations = v_low + v_high
        
        max_line_loading = net.res_line['loading_percent'].max() if len(net.res_line) > 0 else 0
        overloaded_lines = (net.res_line['loading_percent'] > 100).sum() if len(net.res_line) > 0 else 0
        
        total_cost = net.res_cost if hasattr(net, 'res_cost') else 0
        
        return {
            'converged': hasattr(net, 'OPF_converged') and net.OPF_converged,
            'solve_time_s': solve_time,
            'total_gen_mw': total_gen_domestic,
            'total_load_mw': fixed_load,
            'storage_discharge_mw': storage_discharge,
            'storage_charge_mw': storage_charge,
            'net_import_mw': net_import,
            'gen_load_ratio': scenario_info['gen_load_ratio'],
            'renewable_gen_mw': scenario_info['renewable_gen_mw'],
            'renewable_pct': scenario_info['renewable_pct'],
            'total_cost_eur_per_h': total_cost,
            'line_losses_mw': total_losses,
            'loss_pct': (total_losses / fixed_load * 100) if fixed_load > 0 else 0,
            'max_line_loading_pct': max_line_loading,
            'overloaded_lines': overloaded_lines,
            'voltage_violations': voltage_violations
        }
    except Exception as e:
        print(f"Error in calculation: {e}")
        return {}

def print_scenario_summary(results):
    cost = results.get('total_cost_eur_per_h', 0)
    losses = results.get('line_losses_mw', 0)
    loss_pct = results.get('loss_pct', 0)
    gen = results.get('total_gen_mw', 0)
    load = results.get('total_load_mw', 0)
    stor_dis = results.get('storage_discharge_mw', 0)
    stor_chg = results.get('storage_charge_mw', 0)
    imp = results.get('net_import_mw', 0)

    print(f"\n  Key Results (Post-OPF):")
    print(f"    Total Cost:        {cost:>10,.0f} €/h")
    print(f"    Domestic Gen:      {gen:>10.1f} MW")
    print(f"    Storage Discharge: {stor_dis:>10.1f} MW (+)")
    print(f"    Net Import:        {imp:>10.1f} MW")
    print(f"    Fixed Load:        {load:>10.1f} MW")
    print(f"    Storage Charge:    {stor_chg:>10.1f} MW (-)")
    print(f"    Losses:            {losses:>10.1f} MW ({loss_pct:.2f}%)")
    print(f"    Max Line Loading:  {results.get('max_line_loading_pct',0):>10.1f}%")
    
    if results.get('overloaded_lines', 0) > 0:
        print(f"    ⚠ Overloaded Lines: {results['overloaded_lines']}")

def print_comparison_table(df):
    if df.empty: return
    display_cols = [
        'scenario', 'gen_load_ratio', 'total_cost_eur_per_h', 
        'line_losses_mw', 'loss_pct', 'max_line_loading_pct',
        'voltage_violations', 'converged', 'solve_time_s'
    ]
    df_display = df[display_cols].copy()
    df_display['scenario'] = df_display['scenario'].str.replace('_', ' ').str.title()
    
    print(f"{'Scenario':<25} {'Gen/Load':>9} {'Cost(€/h)':>12} {'Loss(MW)':>10} "
          f"{'Loss%':>7} {'MaxLoad%':>9} {'VViol':>6} {'Status':>8} {'Time(s)':>8}")
    print("─" * 120)
    
    for _, row in df_display.iterrows():
        status = "✓" if row['converged'] else "✗"
        cost_str = f"{row['total_cost_eur_per_h']:,.0f}" if pd.notna(row['total_cost_eur_per_h']) else "N/A"
        loss_mw_str = f"{row['line_losses_mw']:>10.1f}" if pd.notna(row['line_losses_mw']) else "N/A"
        loss_pct_str = f"{row['loss_pct']:>7.2f}" if pd.notna(row['loss_pct']) else "N/A"
        max_load_str = f"{row['max_line_loading_pct']:>9.1f}" if pd.notna(row['max_line_loading_pct']) else "N/A"
        vviol_str = f"{row['voltage_violations']:>6.0f}" if pd.notna(row['voltage_violations']) else "N/A"

        print(f"{row['scenario']:<25} "
              f"{row['gen_load_ratio']:>9.3f} "
              f"{cost_str:>12} "
              f"{loss_mw_str:>10} "
              f"{loss_pct_str:>7} "
              f"{max_load_str:>9} "
              f"{vviol_str:>6} "
              f"{status:>8} "
              f"{row['solve_time_s']:>8.1f}")

if __name__ == "__main__":
    main()