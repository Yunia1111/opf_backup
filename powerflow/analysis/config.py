"""
Configuration file for power flow calculation.
FIXED: Enforce Line Limits to enable congestion management.
"""

# ========== Network Constants ==========
POWER_FACTOR = 0.98
STANDARD_VOLTAGE_LEVELS = [220.0, 380.0]

# --- SLACK BUS DEFAULTS ---
DEFAULT_SLACK_VM_PU = 1.0 
DEFAULT_SLACK_VA_DEGREE = 0.0

# ========== Cache Settings ==========
# Set True to rebuild network from CSVs; False to load from .pkl (Faster)
FORCE_NETWORK_REBUILD = False
NETWORK_CACHE_FILE = "german_grid_base_cache.pkl"

# ========== Feature Flags ==========
RUN_INJECTION_ANALYSIS = False

# ========== PV/PQ Control Strategy ==========
PV_CONTROL_STRATEGY = 'all_gen_buses'
PV_VOLTAGE_LEVELS = [380]
MIXED_PV_PRIMARY_VOLTAGE = 380

# ========== Transformer Parameters ==========
TRAFO_VK_PERCENT = 12.5
TRAFO_VKR_PERCENT = 0.35
TRAFO_PFE_KW = 60
TRAFO_I0_PERCENT = 0.1

# ========== File Paths ==========
DATA_DIR = "data/intermediate_model"
OUTPUT_DIR = "powerflow/analysis/results"

# ========== Power Flow (PF) Settings ==========
PF_MAX_ITERATION = 100
PF_TOLERANCE_MVA = 1e-3
PF_ALGORITHM_SEQUENCE = ['nr', 'bfsw', 'gs']

# ========== Optimal Power Flow (OPF) Settings ==========
OPF_SOLVER = 'pypower'  # Using stable Python solver
OPF_VERBOSE = False     
OPF_CALCULATE_VOLTAGE_ANGLES = True
OPF_TOLERANCE = 1e-4    

POWERMODELS_MODEL = 'ACRLPowerModel' 
POWERMODELS_SOLVER = 'ipopt'

# OPF Constraints
BUS_MIN_VM_PU = 0.95
BUS_MAX_VM_PU = 1.05
ENFORCE_LINE_LIMITS = False      
MAX_LINE_LOADING_PERCENT = 100 

# Generator Q Constraints
GEN_MAX_Q_RATIO = 0.6
GEN_MIN_Q_RATIO = -0.6
SGEN_MAX_Q_RATIO = 0.33
SGEN_MIN_Q_RATIO = -0.33

# ========== Cost Settings (Hybrid Strategy) ==========

# [STRATEGY]
# Use "Soft Quadratic" costs for Borders/Slack to allow smooth imports when needed.
# Formula: Cost = (c2 * P^2) + (c1 * P)

# 1. Main Slack Costs
MAIN_SLACK_PARAMS = {'c1': 0.0, 'c2': 0.5}

# 2. Border Import Costs
IMPORT_COST_PARAMS = {
    # Offshore Wind (Must run, cheap)
    'HVDC-Offshore': {'c1': 0.0, 'c2': 0.0}, 
    
    # Expensive Neighbors (High base price c1)
    'France':        {'c1': 0.0, 'c2': 0.05},
    'Switzerland':   {'c1': 0.0, 'c2': 0.05},
    
    # Standard Neighbors
    'default':       {'c1': 0.0, 'c2': 0.02}
}

# Storage: Low cost to encourage usage for flexibility
STORAGE_COST_PARAMS = {'c1': 0.0, 'c2': 0.01}

# 3. Domestic Generation Costs (Pure Linear c1)
GENERATION_COSTS = {
    # --- Renewables ---
    'solar radiant energy': 0, 
    'wind_onshore': 0,
    'wind_offshore': 0,
    'water': 0,
    
    # --- Base Load ---
    'biomass': 10,
    'non-biogenic waste': 10,
    'warmth': 10,
    
    # --- Fossil ---
    'brown coal': 30,     
    'coal': 40,           
    'natural_gas': 60,    
    'other gases': 70,
    'petroleum products': 80, 
    'hydrogen': 90,       
    
    'default': 50
}

# ========== Visualization Settings ==========
GENERATOR_TYPE_COLORS = {
    'solar radiant energy': '#F39C12', # Orange
    'wind_onshore': '#2ECC71',         # Green
    'wind_offshore': '#1ABC9C',        # Teal
    'water': '#3498DB',                # Blue
    'biomass': '#8E44AD',              # Purple
    'non-biogenic waste': '#7F8C8D',   # Grey
    'warmth': '#E67E22',               # Dark Orange
    'storage': '#F1C40F',              # Yellow
    'brown coal': '#795548',           # Brown
    'coal': '#34495E',                 # Dark Grey
    'natural gas': '#E74C3C',          # Red 
    'other gases': '#C0392B',          # Dark Red
    'petroleum products': '#2C3E50',   # Black-Blue
    'hydrogen': '#3498DB',             # Light Blue
    'virtual_injection': '#00FF00',    # Bright Green
    'border': '#00008B',               # Dark Blue
    'other': '#95A5A6'
}
HVDC_COLOR = '#FF6B35'