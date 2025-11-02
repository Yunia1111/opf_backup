"""
Configuration file for power flow calculation
"""

# ========== Power Flow Settings ==========
POWER_FACTOR = 0.98

# Generator capacity factors
GENERATION_CAPACITY_FACTORS = {
    'wind_offshore': 0.5,
    'wind_onshore': 0.3,
    'solar_radiant_energy': 0.3,
    'water': 0.401,
    'biomass': 0.497,
    'natural_gas': 0.620,
    'petroleum_products': 0.200,
    'other_gases': 0.600,
    'warmth': 0.675,
    'non_biogenic_waste': 0.725,
    'storage': 0.150,
    # Fallback patterns
    'wind': 0.30,
    'solar': 0.15,
    'hydro': 0.40,
    'gas': 0.60,
    'other': 0.50
}

# Overall scaling factors
GENERATION_SCALING_FACTOR = 0.5  # Overall generation scaling (after capacity factors)
LOAD_SCALING_FACTOR = 1          # Overall load scaling

# ========== Network Settings ==========
REMOVE_DC_BUSES = True
STANDARD_VOLTAGE_LEVELS = [220.0, 380.0]

# ========== PV/PQ Control Strategy ==========
# Strategy options: 'voltage_based', 'mixed'
PV_CONTROL_STRATEGY = 'voltage_based'

# Strategy 1: voltage_based - Only specific voltage levels are PV (excluding ext_grid buses)
PV_VOLTAGE_LEVELS = [380]  # kV levels that use PV control

# Strategy 2: mixed - Primary voltage level + ratio of secondary voltage level
MIXED_PV_PRIMARY_VOLTAGE = 380       # Primary PV voltage level (kV)
MIXED_PV_SECONDARY_VOLTAGE = 220     # Secondary PV voltage level (kV)
MIXED_PV_SECONDARY_RATIO = 0.3       # Ratio of secondary voltage generators to set as PV (0.0-1.0)
MIXED_PV_SELECTION_METHOD = 'largest'  # 'largest': select largest capacity, 'distributed': select evenly distributed

# ========== Transformer Parameters ==========
TRAFO_VK_PERCENT = 12.5
TRAFO_VKR_PERCENT = 0.35
TRAFO_PFE_KW = 60
TRAFO_I0_PERCENT = 0.1

# ========== Convergence Settings ==========
MAX_ITERATION = 100
TOLERANCE_MVA = 1e-3  # Relaxed for better convergence (was 1e-6)
ALGORITHM_SEQUENCE = ['nr', 'bfsw', 'gs']

# ========== Slack Bus Selection ==========
SLACK_REFERENCE_LAT = 50.1
SLACK_REFERENCE_LON = 8.7
SLACK_BORDER_THRESHOLD_KM = 50

DEFAULT_SLACK_VM_PU = 1.0
DEFAULT_SLACK_VA_DEGREE = 0.0

# ========== File Paths ==========
DATA_DIR = "data/intermediate_model/"
OUTPUT_DIR = "results/"

BUSES_FILE = "buses.csv"
CONNECTIONS_FILE = "connections.csv"
GENERATORS_FILE = "generators.csv"
LOADS_FILE = "loads.csv"
TRANSFORMERS_FILE = "transformers.csv"
EXTERNAL_GRIDS_FILE = "external_grids.csv"

# ========== Visualization Settings ==========
VOLTAGE_COLORS = {
    220: '#3498db',
    380: '#9b59b6'
}

LOADING_COLORS = {
    'normal': '#2ecc71',
    'warning': '#f39c12',
    'overload': '#e74c3c',
    'critical': '#c0392b'
}

# Detailed generator type colors for visualization
GENERATOR_TYPE_COLORS = {
    'wind_offshore': "#069589",      # Deep blue
    'wind_onshore': "#35d9bd",       # Light blue
    'solar_radiant_energy': '#F39C12', # Orange/yellow
    'water': "#063388",              # Teal (hydro)
    'biomass': "#6cf8a7",            # Green
    'natural_gas': "#9b4b06",        # Dark orange
    'petroleum_products': '#34495e', # Dark gray
    'other_gases': '#95a5a6',        # Light gray
    'warmth': '#e74c3c',             # Red
    'non_biogenic_waste': '#8e44ad', # Purple
    'storage': '#f1c40f',            # Yellow
    # Fallback colors for general categories
    'wind': "#0b958a",
    'solar': '#f39c12',
    'hydro': "#094086",
    'gas': '#e67e22',
    'coal': '#34495e',
    'nuclear': '#e74c3c',
    'other': '#95a5a6'
}

# HVDC external grid colors
HVDC_COLOR = '#FF6B35'  # Bright orange for HVDC connections

BUS_SIZE_BASE = 5
GENERATOR_SIZE_BASE = 8
EXTERNAL_GRID_SIZE = 12