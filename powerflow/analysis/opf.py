"""
OPF - Manages scenario application, OPF cost/constraint setup, and power flow solving.
ROBUST VERSION: Reverts rigid 'Must-Run' constraints to allow convergence under line limits.
"""
import copy
import pandas as pd
import pandapower as pp
import numpy as np
import warnings
import os
import sys
from . import config
from .scenarios import SCENARIOS

# Filter warnings
warnings.filterwarnings('ignore', message='.*numba.*')
warnings.filterwarnings('ignore', category=FutureWarning, message='.*Downcasting.*')

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
        if self.logfile: self.logfile.close()

class OPFEngine:
    def __init__(self, base_net, external_grids):
        self.base_net = base_net
        self.external_grids = external_grids
        self.scenarios = SCENARIOS
        self.scenario_net = None
        self.scenario_info = None
        self.current_scenario_name = None
        self.current_scenario_config = None

    def run_scenario(self, scenario_input):
        # 1. Input Handling
        if isinstance(scenario_input, str):
            if scenario_input not in self.scenarios:
                raise ValueError(f"Scenario '{scenario_input}' not found.")
            self.current_scenario_name = scenario_input
            self.current_scenario_config = self.scenarios[scenario_input]
        elif isinstance(scenario_input, dict):
            self.current_scenario_name = scenario_input.get('name', 'custom_run')
            self.current_scenario_config = scenario_input
        else:
            raise TypeError("scenario_input must be a string or a dictionary.")
        
        # 2. Apply Scenario
        self.scenario_net, self.scenario_info = self._apply_scenario(self.current_scenario_config)
        
        # 3. Setup OPF (Costs & Constraints)
        self._setup_opf_costs()
        
        # 4. Solve
        log_file = os.path.join(config.OUTPUT_DIR, self.current_scenario_name, 'opf_log.txt')
        try:
            with OutputRedirector(log_file):
                converged = self._solve_opf()
        except Exception as e:
            print(f"Log redirect warning: {e}")
            converged = self._solve_opf()
        
        return self.scenario_net, self.scenario_info, converged

    def _apply_scenario(self, scenario_data):
        net = copy.deepcopy(self.base_net)
        cfs = scenario_data.get('capacity_factors', {})
        load_scale = scenario_data.get('load_scale', 1.0)
        
        # Get Storage Mode (default to bidirectional if missing)
        storage_mode = scenario_data.get('storage_mode', 'bidirectional')
        
        total_gen_breakdown = {}

        # Apply CFs
        def apply_cf_to_table(df, et_type):
            if len(df) == 0: return
            
            # Ensure columns exist
            if 'max_p_mw' not in df.columns: df['max_p_mw'] = df['p_mw']
            if 'min_p_mw' not in df.columns: df['min_p_mw'] = 0.0
            
            for idx in df.index:
                # Border generators handled separately
                if str(df.at[idx, 'type']) == 'border': continue

                # Determine Nameplate
                install_cap = df.at[idx, 'max_p_mw']
                if pd.isna(install_cap) or install_cap <= 0:
                    install_cap = df.at[idx, 'p_mw']
                
                gen_type = str(df.at[idx, 'type'])
                cf = cfs.get(gen_type, 1.0) # Default to 1.0
                
                actual_p = install_cap * cf
                
                # Update P value for display/init
                df.at[idx, 'p_mw'] = actual_p
                
                # --- Update Limits & Flexibility ---
                if et_type == 'storage':
                    # STORAGE LOGIC based on MODE
                    if storage_mode == 'charge_only':
                        # Can only consume power (-Cap to 0)
                        df.at[idx, 'max_p_mw'] = 0.0
                        df.at[idx, 'min_p_mw'] = -actual_p
                    
                    elif storage_mode == 'discharge_only':
                        # Can only generate power (0 to +Cap)
                        df.at[idx, 'max_p_mw'] = actual_p
                        df.at[idx, 'min_p_mw'] = 0.0
                    
                    else: # 'bidirectional' (default)
                        # Can do both (-Cap to +Cap) to fix congestion
                        df.at[idx, 'max_p_mw'] = actual_p
                        df.at[idx, 'min_p_mw'] = -actual_p

                else:
                    # GENERATOR LOGIC (Relaxed for Convergence):
                    # Set max to available power (CF * Cap)
                    df.at[idx, 'max_p_mw'] = actual_p
                    # Set min to 50% of actual_p to allow flexibility
                    df.at[idx, 'min_p_mw'] = 0.5 * actual_p 

                # Track Stats
                if gen_type not in total_gen_breakdown: total_gen_breakdown[gen_type] = 0
                total_gen_breakdown[gen_type] += actual_p

        apply_cf_to_table(net.gen, 'gen')
        apply_cf_to_table(net.sgen, 'sgen')
        apply_cf_to_table(net.storage, 'storage')
        
        # Load Scaling
        net.load['scaling'] = load_scale
        net.load['p_mw'] *= load_scale
        net.load['q_mvar'] *= load_scale

        total_gen = sum(total_gen_breakdown.values())
        total_load = net.load['p_mw'].sum()
        
        info = {
            'name': self.current_scenario_name,
            'description': scenario_data.get('description', ''),
            'total_load_mw': total_load,
            'total_gen_mw': total_gen,
            'gen_by_type': total_gen_breakdown,
            'load_scale': load_scale
        }
        return net, info

    def _setup_opf_costs(self):
        """
        Sets up costs and constraints.
        """
        net = self.scenario_net
        scen = self.current_scenario_config
        
        # --- 1. Voltage Limits ---
        net.bus['min_vm_pu'] = config.BUS_MIN_VM_PU
        net.bus['max_vm_pu'] = config.BUS_MAX_VM_PU
        
        # --- 2. Q Constraints ---
        
        # A. Generators
        if len(net.gen) > 0:
            if 'min_q_mvar' not in net.gen.columns: net.gen['min_q_mvar'] = np.nan
            if 'max_q_mvar' not in net.gen.columns: net.gen['max_q_mvar'] = np.nan
            
            for idx, gen in net.gen.iterrows():
                if str(gen['type']) == 'border':
                    q_limit = gen['sn_mva'] * 0.6 if pd.notna(gen['sn_mva']) else 9999
                    net.gen.at[idx, 'min_q_mvar'] = -q_limit
                    net.gen.at[idx, 'max_q_mvar'] = q_limit
                else:
                    sn = gen['sn_mva'] if pd.notna(gen['sn_mva']) else gen['p_mw'] / 0.9
                    net.gen.at[idx, 'min_q_mvar'] = sn * config.GEN_MIN_Q_RATIO * 0.8
                    net.gen.at[idx, 'max_q_mvar'] = sn * config.GEN_MAX_Q_RATIO

        # B. Static Generators
        if len(net.sgen) > 0:
            net.sgen['min_q_mvar'] = net.sgen['p_mw'] * config.SGEN_MIN_Q_RATIO * 0.8
            net.sgen['max_q_mvar'] = net.sgen['p_mw'] * config.SGEN_MAX_Q_RATIO
            
        # C. Storage
        if len(net.storage) > 0:
            storage_q_ratio = 0.3
            if 'sn_mva' not in net.storage.columns: net.storage['sn_mva'] = net.storage['p_mw']
            net.storage['min_q_mvar'] = -net.storage['sn_mva'] * storage_q_ratio
            net.storage['max_q_mvar'] = net.storage['sn_mva'] * storage_q_ratio

        # --- 3. Line Limits ---
        if config.ENFORCE_LINE_LIMITS and len(net.line) > 0:
            net.line['max_loading_percent'] = config.MAX_LINE_LOADING_PERCENT

        # --- 4. Cost Application (Dynamic from Scenario) ---
        
        # Clear existing poly costs
        net.poly_cost.drop(net.poly_cost.index, inplace=True)

        # Prepare Cost Dicts
        active_gen_costs = config.GENERATION_COSTS.copy()
        if 'generation_costs' in scen: active_gen_costs.update(scen['generation_costs'])
            
        active_import_costs = config.IMPORT_COST_PARAMS.copy()
        if 'import_costs' in scen: active_import_costs.update(scen['import_costs'])
        
        default_cost_c1 = active_gen_costs.get('default', 50)
        
        for et in ['gen', 'sgen', 'storage']:
            if len(net[et]) > 0:
                for idx, element in net[et].iterrows():
                    # [CRITICAL] Check if in_service to prevent IndexErrors
                    if not element.get('in_service', True): continue

                    gen_type = str(element['type']).lower().strip()
                    
                    if gen_type == 'border':
                        country = element['name'].replace('Border_', '')
                        params = active_import_costs.get('default', {'c1':0, 'c2':0.02})
                        for k, v in active_import_costs.items():
                            if k in country:
                                params = v
                                break
                        pp.create_poly_cost(net, element=idx, et=et, 
                                            cp0_eur=0, cp1_eur_per_mw=params['c1'], cp2_eur_per_mw2=params.get('c2', 0.001))
                                            
                    elif et == 'storage':
                        s_params = config.STORAGE_COST_PARAMS
                        pp.create_poly_cost(net, element=idx, et=et, 
                                            cp0_eur=0, cp1_eur_per_mw=s_params['c1'], cp2_eur_per_mw2=s_params['c2'])
                    else:
                        cost = self._match_generation_cost(gen_type, active_gen_costs, default_cost_c1)
                        pp.create_poly_cost(net, element=idx, et=et, cp1_eur_per_mw=cost)
        
        # DCLines Cost - [CRITICAL] Check in_service
        if len(net.dcline) > 0:
            for idx, dcl in net.dcline.iterrows():
                if dcl.get('in_service', True):
                    pp.create_poly_cost(net, element=idx, et='dcline', cp1_eur_per_mw=1.0)
                
        # Main Slack (External Grid) - Make it Controllable!
        net.ext_grid['controllable'] = True
        slack_params = config.MAIN_SLACK_PARAMS 
        c1_slack = slack_params.get('c1', 1000) if slack_params else 1000
        c2_slack = slack_params.get('c2', 0.1) if slack_params else 0.1
        
        for idx in net.ext_grid.index:
             if net.ext_grid.at[idx, 'in_service']:
                pp.create_poly_cost(net, element=idx, et='ext_grid', 
                                    cp0_eur=0, cp1_eur_per_mw=c1_slack, cp2_eur_per_mw2=c2_slack)     

    def _match_generation_cost(self, gen_type, cost_dict, default_val):
        gen_type_clean = gen_type.replace('_', ' ').replace('-', ' ')
        if gen_type in cost_dict: return cost_dict[gen_type]
        for key in cost_dict:
            if key in gen_type: return cost_dict[key]
            key_clean = key.replace('_', ' ').replace('-', ' ')
            if key_clean in gen_type_clean or gen_type_clean in key_clean: return cost_dict[key]
        return default_val

    def _solve_opf(self):
        net = self.scenario_net
        
        # Warm Start Logic
        print("--- WARM START: Calculating initial power flow (PF) ---")
        try:
            pp.runpp(net, algorithm='nr', max_iteration=20, numba=False)
            init_mode = 'results'
            print("  ✓ PF Warm Start successful.")
        except:
            print("  ⚠ PF initialization failed. Using FLAT start.")
            init_mode = 'flat'

        # [FIXED] Safe fillna for numeric columns only to prevent FutureWarning
        for element in [net.gen, net.sgen]:
            num_cols = element.select_dtypes(include=[np.number]).columns
            element[num_cols] = element[num_cols].fillna(0.0)
        
        if 'poly_cost' in net:
            p_cols = net.poly_cost.select_dtypes(include=[np.number]).columns
            net.poly_cost[p_cols] = net.poly_cost[p_cols].fillna(0.0)

        try:
            print(f"--- OPF START (Solver: {config.OPF_SOLVER}) ---")
            pp.runopp(
                net,
                verbose=config.OPF_VERBOSE, 
                calculate_voltage_angles=config.OPF_CALCULATE_VOLTAGE_ANGLES,
                init=init_mode, 
                pm_model=config.POWERMODELS_MODEL, 
                pm_solver=config.POWERMODELS_SOLVER,
                pm_tol=config.OPF_TOLERANCE,
                ignore_ppm=True,
                delta_q=0.01,
                suppress_warnings=True 
            )
            
            # Check success
            is_success = False
            if hasattr(net, 'OPF_converged') and net.OPF_converged: is_success = True
            elif hasattr(net, 'converged') and net.converged: is_success = True
            elif hasattr(net, 'res_cost') and not np.isnan(net.res_cost): is_success = True
            
            if is_success:
                print("--- SOLVER CONVERGED ---")
                return True
            else:
                print("--- SOLVER FAILED TO CONVERGE ---")
                return False
                
        except Exception as e:
            print(f"CRITICAL OPF EXCEPTION: {e}")
            return False