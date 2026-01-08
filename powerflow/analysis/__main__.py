"""
Main program for multi-scenario optimal power flow calculation.
Build Base Net -> Run Scenarios (OPF) -> Summarize.
"""
import sys
import os
import pandas as pd
import numpy as np
import time
import warnings
from . import config
from . import grid_building
from . import opf
from . import report_export

# 忽略不必要的 Pandas 警告
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=UserWarning)

# Try importing scenarios
try:
    from .scenarios import SCENARIOS
except ImportError:
    print("CRITICAL ERROR: 'scenarios.py' not found.")
    sys.exit(1)

def main():
    print("\n" + "="*80)
    print("GERMAN GRID MULTI-SCENARIO OPF ANALYSIS (V2.5 - Robust)")
    print("="*80 + "\n")

    # 1. Load Grid
    # ==============================================================================
    if not os.path.exists(config.DATA_DIR):
        print(f"ERROR: Data directory '{config.DATA_DIR}' not found.")
        sys.exit(1)

    print("[STEP 1/2] Building static base network (net_0)...")
    try:
        modeler = grid_building.GridModeler()
        base_net, external_grids = modeler.create_base_network()
    except Exception as e:
        print(f"CRITICAL: Grid building failed. {e}")
        sys.exit(1)

    # 2. Run Scenarios
    # ==============================================================================
    print("\n" + "="*80)
    print("[STEP 2/2] Running scenarios with OPF Engine...")
    print("="*80 + "\n")

    engine = opf.OPFEngine(base_net, external_grids)
    all_results = []
    
    # 获取场景列表
    scenario_list = list(SCENARIOS.keys())
    scenario_list = ['average_of_2025']
    print(f"Total scenarios to run: {len(scenario_list)}")
    print(f"Scenarios: {', '.join(scenario_list)}")

    for i, scen_name in enumerate(scenario_list):
        print(f"\n" + "─"*80)
        print(f"[{i+1}/{len(scenario_list)}] SCENARIO: {scen_name.upper()}")
        
        start_t = time.time()
        
        # --- A. 初始化结果字典 (默认全是 NaN) ---
        # 这样即使计算失败，Key 也存在，不会报 KeyError
        res = {
            'scenario': scen_name,
            'converged': False,
            'solve_time_s': 0.0,
            'total_cost_eur_per_h': np.nan,
            'total_load_mw': np.nan,
            'total_gen_mw': np.nan,
            'gen_load_ratio': np.nan,
            'net_import_mw': np.nan,
            'line_losses_mw': np.nan,
            'loss_pct': np.nan,
            'max_line_loading_pct': np.nan,
            'voltage_violations': 0,
            'num_lines_overloaded': 0
        }

        try:
            # --- B. 运行 OPF ---
            # run_scenario 现在支持处理字符串或字典
            net, info, converged = engine.run_scenario(scen_name)
            duration = time.time() - start_t
            
            res['converged'] = converged
            res['solve_time_s'] = round(duration, 2)

            # --- C. 提取结果 (仅在收敛且有结果时) ---
            if converged and not net.res_line.empty:
                # 1. 成本
                res['total_cost_eur_per_h'] = net.res_cost

                # 2. 负荷与发电 (直接从 info 获取更安全)
                res['total_load_mw'] = info.get('total_load_mw', 0.0)
                res['total_gen_mw'] = info.get('total_gen_mw', 0.0)
                
                # 3. 比例与进口
                if res['total_load_mw'] > 0:
                    res['gen_load_ratio'] = (res['total_gen_mw'] / res['total_load_mw']) * 100
                else:
                    res['gen_load_ratio'] = 0.0
                
                res['net_import_mw'] = res['total_load_mw'] - res['total_gen_mw']

                # 4. 线路损耗
                res['line_losses_mw'] = net.res_line['pl_mw'].sum()
                if res['total_load_mw'] > 0:
                    res['loss_pct'] = (res['line_losses_mw'] / res['total_load_mw']) * 100
                
                # 5. 负载率
                res['max_line_loading_pct'] = net.res_line['loading_percent'].max()
                res['num_lines_overloaded'] = len(net.res_line[net.res_line['loading_percent'] > 100])

                # 6. 电压违规 (0.90 - 1.10 pu)
                v_violations = len(net.res_bus[(net.res_bus['vm_pu'] < 0.90) | (net.res_bus['vm_pu'] > 1.10)])
                res['voltage_violations'] = v_violations

                # 7. 导出报告
                exporter = report_export.ReportGenerator(net)
                exporter.export_all(scen_name)
                
                print(f"  ✓ Converged. Cost: {res['total_cost_eur_per_h']:,.0f} €/h")

            else:
                print(f"  ✗ Scenario {scen_name} FAILED to converge. Skipping extraction.")

        except Exception as e:
            print(f"  ✗ Error calculating results for {scen_name}: {e}")
            import traceback
            traceback.print_exc()
            # 即使报错，res 字典里也有默认值，不会导致后续表格崩溃
        
        all_results.append(res)

    # 3. Summary Table
    # ==============================================================================
    if len(all_results) > 0:
        df_results = pd.DataFrame(all_results)
        print_comparison_table(df_results)
        
        # Save Summary CSV
        sum_path = os.path.join(config.OUTPUT_DIR, 'scenario_comparison_summary.csv')
        df_results.to_csv(sum_path, index=False)
        print(f"\nFull comparison saved to: {sum_path}")
    else:
        print("\nNo results generated.")

def print_comparison_table(df):
    """
    Prints a nicely formatted ASCII table of the results.
    Handles NaN/None values gracefully.
    """
    print("\n" + "="*80)
    print("SCENARIO COMPARISON SUMMARY")
    print("="*80 + "\n")
    
    # 确保需要的列都在 (防止 KeyError)
    needed_cols = [
        'scenario', 'gen_load_ratio', 'total_cost_eur_per_h',
        'line_losses_mw', 'loss_pct', 'max_line_loading_pct',
        'voltage_violations', 'converged', 'solve_time_s'
    ]
    
    # 检查缺失列并补全
    for col in needed_cols:
        if col not in df.columns:
            df[col] = np.nan

    # 格式化打印
    header = f"{'Scenario':<25} {'Gen/Load%':>10} {'Cost(€/h)':>12} {'Loss(MW)':>10} {'Loss%':>7} {'MaxLoad%':>9} {'VViol':>6} {'Status':>8} {'Time':>6}"
    print(header)
    print("─" * 100)

    for _, row in df.iterrows():
        # 处理可能的 NaN
        status = "✓" if row['converged'] else "✗"
        
        def fmt(val, precision=1, use_comma=False):
            if pd.isna(val): return "N/A"
            if use_comma: return f"{val:,.0f}"
            return f"{val:.{precision}f}"

        scen_label = row['scenario'].replace('_', ' ').title()[:24]
        
        line = (
            f"{scen_label:<25} "
            f"{fmt(row['gen_load_ratio']):>10} "
            f"{fmt(row['total_cost_eur_per_h'], 0, True):>12} "
            f"{fmt(row['line_losses_mw']):>10} "
            f"{fmt(row['loss_pct'], 2):>7} "
            f"{fmt(row['max_line_loading_pct']):>9} "
            f"{fmt(row['voltage_violations'], 0):>6} "
            f"{status:>8} "
            f"{fmt(row['solve_time_s']):>6}"
        )
        print(line)
    print("─" * 100)

if __name__ == "__main__":
    main()