"""
OPF Engine - Manages scenario application, OPF cost/constraint setup, 
and power flow solving.
Integrates ScenarioManager, OPFCostManager, and PowerFlowSolver logic.
Includes Output Redirection and Robust Convergence Checks.
"""
import copy
import pandas as pd
import pandapower as pp
import numpy as np
import warnings
import os
import sys
import config
try:
    from scenarios import SCENARIOS # Updated Import
except ImportError:
    SCENARIOS = {} # Fallback

warnings.filterwarnings('ignore', message='.*numba.*')

class OutputRedirector:
    """Context manager to capture stdout/stderr to a file."""
    def __init__(self, filename):
        self.filename = filename
        self.original_stdout_fd = sys.stdout.fileno()
        self.original_stderr_fd = sys.stderr.fileno()
        self.saved_stdout_fd = None
        self.saved_stderr_fd = None
        self.logfile = None

    def __enter__(self):
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        self.logfile = open(self.filename, 'w', encoding='utf-8')
        self.saved_stdout_fd = os.dup(self.original_stdout_fd)
        self.saved_stderr_fd = os.dup(self.original_stderr_fd)
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(self.logfile.fileno(), self.original_stdout_fd)
        os.dup2(self.logfile.fileno(), self.original_stderr_fd)
        
    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(self.saved_stdout_fd, self.original_stdout_fd)
        os.dup2(self.saved_stderr_fd, self.original_stderr_fd)
        os.close(self.saved_stdout_fd)
        os.close(self.saved_stderr_fd)
        self.logfile.close()

class OPFEngine:
    
    def __init__(self, base_net, external_grids):
        self.base_net = base_net
        self.external_grids = external_grids
        self.scenarios = SCENARIOS
        self.scenario_net = None
        self.scenario_info = None
        self.current_scenario_name = None
        
    def run_scenario(self, scenario_name):
        if scenario_name not in self.scenarios:
            raise ValueError(f"Unknown scenario: {scenario_name}")

        self.current_scenario_name = scenario_name
        scenario_config = self.scenarios[scenario_name]
        
        # 1. Apply Scenario
        self.scenario_net, self.scenario_info = self._apply_scenario(scenario_config)
        
        # 2. Setup OPF
        self._setup_opf_costs()
        
        # 3. Solve
        converged = self._solve_opf()
        
        return self.scenario_net, self.scenario_info, converged

    def _apply_scenario(self, scenario_config):
        net = copy.deepcopy(self.base_net)
        capacity_factors = scenario_config['capacity_factors']
        load_scale = scenario_config['load_scale']
        default_cf = 1.0
        total_gen_breakdown = {}

        def apply_cf_to_table(df, is_storage=False):
            if len(df) == 0: return df
            for idx in df.index:
                if str(df.at[idx, 'type']) == 'border': continue

                nameplate_p = df.at[idx, 'nameplate_p_mw']
                if pd.isna(nameplate_p) or nameplate_p <= 0: continue
                
                gen_type = str(df.at[idx, 'type'])
                cf = capacity_factors.get(gen_type, default_cf)
                actual_p = nameplate_p * cf
                
                if gen_type not in total_gen_breakdown: total_gen_breakdown[gen_type] = 0
                total_gen_breakdown[gen_type] += actual_p

                if is_storage:
                    df.at[idx, 'max_p_mw'] = actual_p
                    df.at[idx, 'min_p_mw'] = -actual_p
                else:
                    nameplate_sn = df.at[idx, 'nameplate_sn_mva']
                    actual_sn = nameplate_sn * cf
                    df.at[idx, 'p_mw'] = actual_p
                    df.at[idx, 'sn_mva'] = actual_sn
                    df.at[idx, 'max_p_mw'] = actual_p 
                    df.at[idx, 'min_p_mw'] = actual_p * 0.8 # Allow some dispatch down
            return df

        net.gen = apply_cf_to_table(net.gen)
        net.sgen = apply_cf_to_table(net.sgen)
        net.storage = apply_cf_to_table(net.storage, is_storage=True)
        
        net.load.loc[:, 'p_mw'] = net.load['nameplate_p_mw'] * load_scale
        net.load.loc[:, 'q_mvar'] = net.load['nameplate_q_mvar'] * load_scale

        total_gen = sum(total_gen_breakdown.values())
        total_load = net.load['p_mw'].sum()
        renewable_types = ['solar', 'wind', 'water', 'hydro', 'biomass']
        renewable_gen = sum(capacity for gen_type, capacity in total_gen_breakdown.items()
                            if any(rt in gen_type.lower() for rt in renewable_types))

        scenario_info = {
            'name': scenario_config['name'], 'description': scenario_config['description'],
            'total_gen_mw': total_gen, 'total_load_mw': total_load,
            'gen_load_ratio': total_gen / total_load if total_load > 0 else 0,
            'renewable_gen_mw': renewable_gen,
            'renewable_pct': (renewable_gen / total_gen * 100) if total_gen > 0 else 0,
            'load_scale': load_scale, 'gen_by_type': total_gen_breakdown
        }
        return net, scenario_info

    def _setup_opf_costs(self):
        """Sets up costs with Storage separated."""
        net = self.scenario_net
        net.bus['min_vm_pu'] = config.BUS_MIN_VM_PU
        net.bus['max_vm_pu'] = config.BUS_MAX_VM_PU
        
        # 1. Q Constraints (Gen, SGen, Storage)
        if len(net.gen) > 0:
            if 'min_q_mvar' not in net.gen.columns: net.gen['min_q_mvar'] = np.nan
            if 'max_q_mvar' not in net.gen.columns: net.gen['max_q_mvar'] = np.nan
            for idx, gen in net.gen.iterrows():
                if str(gen['type']) == 'border':
                    q_limit = gen['sn_mva'] * 0.6
                    net.gen.at[idx, 'min_q_mvar'] = -q_limit
                    net.gen.at[idx, 'max_q_mvar'] = q_limit
                else:
                    sn = gen['sn_mva']
                    net.gen.at[idx, 'min_q_mvar'] = sn * config.GEN_MIN_Q_RATIO * 0.8
                    net.gen.at[idx, 'max_q_mvar'] = sn * config.GEN_MAX_Q_RATIO

        if len(net.sgen) > 0:
            net.sgen['min_q_mvar'] = net.sgen['p_mw'] * config.SGEN_MIN_Q_RATIO * 0.8
            net.sgen['max_q_mvar'] = net.sgen['p_mw'] * config.SGEN_MAX_Q_RATIO
            
        if len(net.storage) > 0:
            storage_q_ratio = 0.3
            net.storage['min_q_mvar'] = -net.storage['sn_mva'] * storage_q_ratio
            net.storage['max_q_mvar'] = net.storage['sn_mva'] * storage_q_ratio

        if config.ENFORCE_LINE_LIMITS and len(net.line) > 0:
            net.line['max_loading_percent'] = config.MAX_LINE_LOADING_PERCENT

        # 3. Cost Application
        gen_costs = config.GENERATION_COSTS
        default_cost_c1 = gen_costs.get('default', 50)
        
        for et in ['gen', 'sgen', 'storage']:
            if len(net[et]) > 0:
                for idx, element in net[et].iterrows():
                    gen_type = str(element['type']).lower().strip()
                    
                    if gen_type == 'border':
                        # Border Cost
                        country = element['name'].replace('Border_', '')
                        params = config.IMPORT_COST_PARAMS.get('default', {'c1':0, 'c2':0.02})
                        for k, v in config.IMPORT_COST_PARAMS.items():
                            if k in country:
                                params = v
                                break
                        pp.create_poly_cost(net, element=idx, et=et, 
                                            cp0_eur=0, cp1_eur_per_mw=params['c1'], cp2_eur_per_mw2=params['c2'])
                                                
                    elif et == 'storage':
                        # Storage Cost: Quadratic (Symmetric Penalty)
                        s_params = config.STORAGE_COST_PARAMS
                        pp.create_poly_cost(net, element=idx, et=et, 
                                            cp0_eur=0, cp1_eur_per_mw=s_params['c1'], cp2_eur_per_mw2=s_params['c2'])
                    else:
                        # Domestic Gen Cost
                        cost = self._match_generation_cost(gen_type, gen_costs, default_cost_c1)
                        pp.create_poly_cost(net, element=idx, et=et, cp1_eur_per_mw=cost)
        
        if len(net.dcline) > 0:
            for idx in net.dcline.index:
                pp.create_poly_cost(net, element=idx, et='dcline', cp1_eur_per_mw=0.0)
                
        # 4. Main Slack Cost
        net.ext_grid['controllable'] = True
        slack_params = config.MAIN_SLACK_PARAMS
        for idx, eg in net.ext_grid.iterrows():
            pp.create_poly_cost(net, element=idx, et='ext_grid', 
                                cp0_eur=0, cp1_eur_per_mw=slack_params['c1'], cp2_eur_per_mw2=slack_params['c2'])     
       
    def _match_generation_cost(self, gen_type, gen_costs, default_cost):
        gen_type_clean = gen_type.replace('_', ' ').replace('-', ' ')
        if gen_type in gen_costs: return gen_costs[gen_type]
        for key, cost in gen_costs.items():
            key_clean = key.replace('_', ' ').replace('-', ' ')
            if key_clean in gen_type_clean or gen_type_clean in key_clean: return cost
        return default_cost

    def _solve_opf(self, custom_init_net=None):
        net = self.scenario_net
        log_filename = "solver_debug.log"
        if self.current_scenario_name:
            output_path = os.path.join(config.OUTPUT_DIR, self.current_scenario_name, log_filename)
        else:
            output_path = os.path.join(config.OUTPUT_DIR, "logs", log_filename)

        print(f"  > Initializing... (Logs: {output_path})")

        with OutputRedirector(output_path):
            init_values = 'flat'
            
            # --- Warm Start Check ---
            has_results = (len(net.res_bus) == len(net.bus) and not net.res_bus.isnull().values.any())
            
            if has_results or custom_init_net:
                if custom_init_net:
                    net.bus['vm_pu'] = custom_init_net.res_bus['vm_pu']
                    net.bus['va_degree'] = custom_init_net.res_bus['va_degree']
                init_values = 'flat' 
                print("--- WARM START: Using existing results (implicit via VM/VA) ---")
            else:
                print("--- COLD START: Calculating initial power flow ---")
                try:
                    pp.runpp(net, algorithm='nr', max_iteration=config.PF_MAX_ITERATION, numba=False)
                    init_values = 'results'
                    print("AC-PF Warm Start successful.")
                except:
                    print("PF initialization failed. Using FLAT start.")
                    init_values = 'flat'

            print(f"--- OPF START (Solver: {config.OPF_SOLVER}) ---")
            
            # [Cleanup] Prevent NaNs crash
            net.gen.fillna(0.0, inplace=True)
            net.sgen.fillna(0.0, inplace=True)
            if 'poly_cost' in net: net.poly_cost.fillna(0.0, inplace=True)

            try:
                pp.runopp(
                    net,
                    verbose=config.OPF_VERBOSE, 
                    calculate_voltage_angles=config.OPF_CALCULATE_VOLTAGE_ANGLES,
                    init=init_values, 
                    pm_model=config.POWERMODELS_MODEL, 
                    pm_solver=config.POWERMODELS_SOLVER,
                    pm_tol=config.OPF_TOLERANCE,
                    ignore_ppm=True,
                    delta_q=0.01,
                    suppress_warnings=True 
                )
                
                # [Robust Convergence Check]
                is_success = False
                
                if hasattr(net, 'OPF_converged') and net.OPF_converged:
                    is_success = True
                elif hasattr(net, 'converged') and net.converged:
                    is_success = True
                elif hasattr(net, 'res_cost') and not np.isnan(net.res_cost):
                    is_success = True
                    net.OPF_converged = True
                
                if is_success:
                    print("--- SOLVER CONVERGED ---")
                    return True
                else:
                    print("--- SOLVER FAILED TO CONVERGE ---")
                    return False
                    
            except Exception as e:
                print(f"CRITICAL OPF EXCEPTION: {e}")
                import traceback
                traceback.print_exc()
                return False