"""
Scenario Definitions - Representative German Grid Scenarios (The 'Standard 10')
Contains Capacity Factors, Load Scaling, and DETAILED BORDER PRICES.
UPDATED FOR 2025 BASELINE.
"""

# ==========================================
# 1. Default Baseline Costs (Reference)
# ==========================================
DEFAULT_GEN_COSTS = {
    'solar radiant energy': 0, 'wind_onshore': 0, 'wind_offshore': 0, 'water': 0,
    'biomass': 50, 'non-biogenic waste': 20, 'warmth': 20,
    'brown coal': 60, 'coal': 80, 'natural gas': 90, 'other gases': 90,
    'petroleum products': 100, 'hydrogen': 120, 'nuclear': 15, 'storage': 5
}

# Helper: Generate defaults (fallback)
def get_neighbor_defaults(price_c1=70.0):
    return {
        'Austria':     {'c1': price_c1, 'c2': 0.01},
        'Belgium':     {'c1': price_c1, 'c2': 0.01},
        'Switzerland': {'c1': price_c1, 'c2': 0.01},
        'Czechia':     {'c1': price_c1, 'c2': 0.01},
        'Denmark':     {'c1': price_c1, 'c2': 0.01},
        'France':      {'c1': price_c1, 'c2': 0.01},
        'Luxembourg':  {'c1': price_c1, 'c2': 0.01},
        'Netherlands': {'c1': price_c1, 'c2': 0.01},
        'Poland':      {'c1': price_c1, 'c2': 0.01},
        'Sweden':      {'c1': price_c1, 'c2': 0.01},
        'Norway':      {'c1': price_c1, 'c2': 0.01},
        'Germany':     {'c1': price_c1, 'c2': 0.01},
        'default':     {'c1': price_c1, 'c2': 0.01}
    }

# ==========================================
# 2. Scenario Definitions
# ==========================================
SCENARIOS = {
    # -------------------------------------------------------------------------
    # SCENARIO 1: BASELINE (2025 Average) - USER UPDATED PRICES
    # -------------------------------------------------------------------------
    'average_of_2025': {
        'name': '1. Average Of 2025 (Baseline)',
        'description': 'Yearly average CFs. Standard balanced prices for 2025.',
        'capacity_factors': {
            'solar radiant energy': 0.11, 'wind_onshore': 0.23, 'wind_offshore': 0.38,
            'biomass': 0.60, 'water': 0.35, 'natural gas': 0.15, 'coal': 0.30, 
            'brown coal': 0.50, 'nuclear': 0.90, 'storage': 0.2, 'other gases': 0.1,
            'petroleum products': 0.1, 'hydrogen': 0.1, 'non-biogenic waste': 0.5, 'warmth': 0.5
        },
        'load_scale': 1.00,
        'generation_costs': DEFAULT_GEN_COSTS.copy(),
        # Updated Prices (~89 EUR DE Reference)
        'import_costs': {
            'Austria':     {'c1': 99, 'c2': 0},
            'Belgium':     {'c1': 82, 'c2': 0.0},
            'Switzerland': {'c1': 101, 'c2': 0.0}, # Expensive
            'Czechia':     {'c1': 97, 'c2': 0.0},
            'Denmark':     {'c1': 82, 'c2': 0.0}, 
            'France':      {'c1': 61, 'c2': 0.0},  # Cheap (Nuclear)
            'Luxembourg':  {'c1': 89, 'c2': 0.0},
            'Netherlands': {'c1': 86, 'c2': 0.0},
            'Poland':      {'c1': 104, 'c2': 0.0}, # Expensive
            'Sweden':      {'c1': 60, 'c2': 0.0},  # Cheap (Hydro)
            'Norway':      {'c1': 65, 'c2': 0.0},  # Cheap (Hydro)
            'Germany':     {'c1': 89, 'c2': 0.0}, 
            'default':     {'c1': 70, 'c2': 0.0}
        }
    },

    # -------------------------------------------------------------------------
    # SCENARIO 2: DUNKELFLAUTE (Extreme Stress)
    # -------------------------------------------------------------------------
    'dunkelflaute': {
        'name': '2. Dunkelflaute (Dark Doldrums)',
        'description': 'Winter, No Wind/Sun. Extreme Scarcity Prices.',
        'capacity_factors': {
            'solar radiant energy': 0.00, 'wind_onshore': 0.05, 'wind_offshore': 0.10,
            'biomass': 0.95, 'water': 0.40, 'natural gas': 0.95, 'coal': 0.95, 
            'brown coal': 0.95, 'nuclear': 0.95, 'storage': 0.5, 'other gases': 0.8,
            'petroleum products': 0.5, 'hydrogen': 0.5, 'non-biogenic waste': 0.9, 'warmth': 0.9
        },
        'load_scale': 1.25,
        'generation_costs': {**DEFAULT_GEN_COSTS, 'natural gas': 180, 'coal': 150},
        'import_costs': get_neighbor_defaults(price_c1=200.0) # Everything very expensive
    },

    # -------------------------------------------------------------------------
    # SCENARIO 3: WINTER STORM (North-South Congestion)
    # -------------------------------------------------------------------------
    'winter_storm': {
        'name': '3. Winter Storm (Grid Congestion)',
        'description': 'Max Wind in North. North neighbors CHEAP, South EXPENSIVE.',
        'capacity_factors': {
            'solar radiant energy': 0.05, 'wind_onshore': 0.95, 'wind_offshore': 1.00,
            'biomass': 0.40, 'water': 0.60, 'natural gas': 0.10, 'coal': 0.20, 
            'brown coal': 0.30, 'nuclear': 0.80, 'storage': 0.1, 'other gases': 0.1,
            'petroleum products': 0.0, 'hydrogen': 0.0, 'non-biogenic waste': 0.5, 'warmth': 0.5
        },
        'load_scale': 1.00,
        'generation_costs': DEFAULT_GEN_COSTS.copy(),
        'import_costs': {
            'Denmark':     {'c1': 5,   'c2': 0.01}, 
            'Sweden':      {'c1': 10,  'c2': 0.01}, 
            'Norway':      {'c1': 10,  'c2': 0.01}, 
            'Netherlands': {'c1': 20,  'c2': 0.01}, 
            'Poland':      {'c1': 40,  'c2': 0.01},
            'Belgium':     {'c1': 30,  'c2': 0.01},
            'Luxembourg':  {'c1': 50,  'c2': 0.01},
            'France':      {'c1': 60,  'c2': 0.01},
            'Czechia':     {'c1': 50,  'c2': 0.01},
            'Austria':     {'c1': 80,  'c2': 0.01}, 
            'Switzerland': {'c1': 85,  'c2': 0.01}, 
            'Germany':     {'c1': 50,  'c2': 0.01},
            'default':     {'c1': 50,  'c2': 0.01}
        }
    },

    # -------------------------------------------------------------------------
    # SCENARIO 4: SUMMER PEAK PV (Voltage Issues)
    # -------------------------------------------------------------------------
    'summer_peak_pv': {
        'name': '4. Summer Voltage Stress',
        'description': 'High Solar, Low Load. Prices crash.',
        'capacity_factors': {
            'solar radiant energy': 0.90, 'wind_onshore': 0.10, 'wind_offshore': 0.20,
            'biomass': 0.30, 'water': 0.20, 'natural gas': 0.05, 'coal': 0.10, 
            'brown coal': 0.15, 'nuclear': 0.70, 'storage': 0.8, 'other gases': 0.05,
            'petroleum products': 0.0, 'hydrogen': 0.0, 'non-biogenic waste': 0.4, 'warmth': 0.1
        },
        'load_scale': 0.60,
        'generation_costs': DEFAULT_GEN_COSTS.copy(),
        'import_costs': get_neighbor_defaults(price_c1=15.0) # Very cheap
    },

    # -------------------------------------------------------------------------
    # SCENARIO 5: EVENING RAMP
    # -------------------------------------------------------------------------
    'evening_ramp': {
        'name': '5. Evening Ramp (Flexibility)',
        'description': 'Sunset. Solar drops, Load peaks. Expensive flexibility needed.',
        'capacity_factors': {
            'solar radiant energy': 0.10, 'wind_onshore': 0.25, 'wind_offshore': 0.35,
            'biomass': 0.80, 'water': 0.70, 'natural gas': 0.70, 'coal': 0.60, 
            'brown coal': 0.70, 'nuclear': 0.90, 'storage': 0.9, 'other gases': 0.4,
            'petroleum products': 0.5, 'hydrogen': 0.1, 'non-biogenic waste': 0.6, 'warmth': 0.6
        },
        'load_scale': 1.15,
        'generation_costs': {**DEFAULT_GEN_COSTS, 'storage': 0},
        'import_costs': get_neighbor_defaults(price_c1=110.0)
    },

    # -------------------------------------------------------------------------
    # SCENARIO 6: TYPICAL WINTER
    # -------------------------------------------------------------------------
    'typical_winter': {
        'name': '6. Typical Winter Day',
        'description': 'January weekday. Standard winter operation.',
        'capacity_factors': {
            'solar radiant energy': 0.10, 'wind_onshore': 0.50, 'wind_offshore': 0.75,
            'biomass': 0.70, 'water': 0.40, 'natural gas': 0.40, 'coal': 0.60, 
            'brown coal': 0.70, 'nuclear': 0.90, 'storage': 0.3, 'other gases': 0.3,
            'petroleum products': 0.1, 'hydrogen': 0.0, 'non-biogenic waste': 0.5, 'warmth': 0.8
        },
        'load_scale': 1.05,
        'generation_costs': DEFAULT_GEN_COSTS.copy(),
        'import_costs': get_neighbor_defaults(price_c1=80.0)
    },

    # -------------------------------------------------------------------------
    # SCENARIO 7: TYPICAL SUMMER
    # -------------------------------------------------------------------------
    'typical_summer': {
        'name': '7. Typical Summer Day',
        'description': 'June weekday. Low prices, moderate load.',
        'capacity_factors': {
            'solar radiant energy': 0.65, 'wind_onshore': 0.15, 'wind_offshore': 0.25,
            'biomass': 0.40, 'water': 0.30, 'natural gas': 0.10, 'coal': 0.20, 
            'brown coal': 0.30, 'nuclear': 0.80, 'storage': 0.1, 'other gases': 0.1,
            'petroleum products': 0.0, 'hydrogen': 0.0, 'non-biogenic waste': 0.4, 'warmth': 0.1
        },
        'load_scale': 0.85,
        'generation_costs': DEFAULT_GEN_COSTS.copy(),
        'import_costs': get_neighbor_defaults(price_c1=45.0)
    },

    # -------------------------------------------------------------------------
    # SCENARIO 8: TRANSITION (Volatility)
    # -------------------------------------------------------------------------
    'transition_mix': {
        'name': '8. Spring/Autumn Volatility',
        'description': 'April/Oct. Windy and Sunny. Prices fluctuate.',
        'capacity_factors': {
            'solar radiant energy': 0.55, 'wind_onshore': 0.60, 'wind_offshore': 0.70,
            'biomass': 0.50, 'water': 0.50, 'natural gas': 0.15, 'coal': 0.20, 
            'brown coal': 0.25, 'nuclear': 0.85, 'storage': 0.4, 'other gases': 0.1,
            'petroleum products': 0.0, 'hydrogen': 0.0, 'non-biogenic waste': 0.4, 'warmth': 0.3
        },
        'load_scale': 0.90,
        'generation_costs': DEFAULT_GEN_COSTS.copy(),
        'import_costs': get_neighbor_defaults(price_c1=40.0)
    },
    
    # -------------------------------------------------------------------------
    # SCENARIO 9: MAX EXPORT (Negative Prices)
    # -------------------------------------------------------------------------
    'high_export': {
        'name': '9. Max Export (Surplus)',
        'description': 'Surplus Generation. Negative prices force export to all neighbors.',
        'capacity_factors': {
            'solar radiant energy': 0.75, 'wind_onshore': 0.85, 'wind_offshore': 0.95,
            'biomass': 0.60, 'water': 0.60, 'natural gas': 0.05, 'coal': 0.10, 
            'brown coal': 0.20, 'nuclear': 0.90, 'storage': 0.5, 'other gases': 0.1,
            'petroleum products': 0.0, 'hydrogen': 0.0, 'non-biogenic waste': 0.4, 'warmth': 0.2
        },
        'load_scale': 0.70,
        'generation_costs': DEFAULT_GEN_COSTS.copy(),
        'import_costs': get_neighbor_defaults(price_c1=-50.0)
    },

    # -------------------------------------------------------------------------
    # SCENARIO 10: FUTURE 2030 (Coal Exit)
    # -------------------------------------------------------------------------
    'future_2030': {
        'name': '10. Future 2030 Stress',
        'description': 'High Load. Coal phase-out. High Carbon Prices.',
        'capacity_factors': {
            'solar radiant energy': 0.10, 'wind_onshore': 0.50, 'wind_offshore': 0.75,
            'biomass': 0.70, 'water': 0.40, 'natural gas': 0.60, 'coal': 0.00, 
            'brown coal': 0.00, 'nuclear': 0.00, 
            'storage': 0.9, 'other gases': 0.5,
            'petroleum products': 0.0, 'hydrogen': 0.5, 'non-biogenic waste': 0.6, 'warmth': 0.8
        },
        'load_scale': 1.35,
        'generation_costs': {
            **DEFAULT_GEN_COSTS,
            'natural gas': 110,
            'coal': 999,      # Phase out
            'brown coal': 999
        },
        'import_costs': get_neighbor_defaults(price_c1=90.0)
    }
}