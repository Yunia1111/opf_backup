"""
Power flow solver - runs power flow with multiple algorithms
IMPROVED VERSION: Added silent mode for incremental building
"""
import pandapower as pp
import warnings
import config

warnings.filterwarnings('ignore', message='.*numba.*')

class PowerFlowSolver:
    def __init__(self, net, silent=False):
        self.net = net
        self.converged = False
        self.algorithm_used = None
        self.silent = silent  # Silent mode for incremental building
        
    def solve(self):
        """Run power flow with fallback algorithms"""
        algorithms = config.ALGORITHM_SEQUENCE
        
        # Try standard settings
        for alg in algorithms:
            try:
                pp.runpp(self.net, algorithm=alg, max_iteration=config.MAX_ITERATION,
                        tolerance_mva=config.TOLERANCE_MVA, init='auto', numba=False)
                if self.net.converged:
                    self.converged = True
                    self.algorithm_used = alg
                    # NO OUTPUT - Silent mode
                    return True
            except:
                continue
                
        # Try relaxed settings
        for alg in ['nr', 'gs']:
            try:
                pp.runpp(self.net, algorithm=alg, max_iteration=500,
                        tolerance_mva=1e-4, init='flat', numba=False)
                if self.net.converged:
                    self.converged = True
                    self.algorithm_used = f"{alg} (relaxed)"
                    # NO OUTPUT - Silent mode
                    return True
            except:
                continue
                
        # Try DC initialization
        try:
            pp.rundcpp(self.net, numba=False)
            pp.runpp(self.net, algorithm='nr', max_iteration=500,
                    tolerance_mva=1e-4, init='results', numba=False)
            if self.net.converged:
                self.converged = True
                self.algorithm_used = "nr (DC-init)"
                # NO OUTPUT - Silent mode
                return True
        except:
            pass
            
        # Failed - only show error if not silent
        if not self.silent:
            print("\n✗ CONVERGENCE FAILED")
            from network_analyzer import NetworkAnalyzer
            analyzer = NetworkAnalyzer(self.net)
            analyzer.diagnose_non_convergence()
        return False
        
    def _print_summary(self):
        """Print convergence summary (only in verbose mode)"""
        # REMOVED - No output in any mode
        pass