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
    'petroleum products': 100, 'hydrogen': 120, 'storage': 5
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
        'name': '1. Average Of 2025',
        'description': 'Yearly average CFs. Standard balanced prices for 2025.',
        'capacity_factors': {
            'solar radiant energy': 0.08, 'wind_onshore': 0.18, 'wind_offshore': 0.46,
            'biomass': 0.45, 'water': 0.30, 'natural gas': 0.15, 'coal': 0.30, 
            'brown coal': 0.48, 'nuclear': 0.90, 'storage': 0.2, 'other gases': 0.1,
            'petroleum products': 0.1, 'hydrogen': 0.1, 'non-biogenic waste': 0.5, 'warmth': 0.5
        },
        'load_scale': 1.00,
        'generation_costs': DEFAULT_GEN_COSTS.copy(),
        'import_costs': {
            'Austria':     {'c1': 99, 'c2': 0.01},
            'Belgium':     {'c1': 82, 'c2': 0.01},
            'Switzerland': {'c1': 101, 'c2': 0.01}, # Expensive
            'Czechia':     {'c1': 97, 'c2': 0.01},
            'Denmark':     {'c1': 82, 'c2': 0.01}, 
            'France':      {'c1': 61, 'c2': 0.01},  # Cheap (Nuclear)
            'Luxembourg':  {'c1': 89, 'c2': 0.01},
            'Netherlands': {'c1': 86, 'c2': 0.01},
            'Poland':      {'c1': 104, 'c2': 0.01}, # Expensive
            'Sweden':      {'c1': 60, 'c2': 0.01},  # Cheap (Hydro)
            'Norway':      {'c1': 65, 'c2': 0.01},  # Cheap (Hydro)
            'Germany':     {'c1': 89, 'c2': 0.01}, 
            'default':     {'c1': 70, 'c2': 0.01}
        }
    },

    # -------------------------------------------------------------------------
    # SCENARIO 2: DUNKELFLAUTE 20250118
    # -------------------------------------------------------------------------
    'dunkelflaute': {
        'name': '2. Dunkelflaute',
        'description': 'Winter, No Wind/Sun. Extreme Scarcity Prices.',
        'capacity_factors': {
            'solar radiant energy': 0.03,
            'wind_onshore': 0.04,
            'biomass': 0.49,
            'wind_offshore': 0.13,
            'water': 0.35,
            'warmth': 0.19,
            'non-biogenic waste': 0.34,
            'hydrogen': 0.01,
            'natural gas': 0.40,
            'coal': 0.34,
            'brown coal': 0.66,
            'petroleum products': 0.12,
            'other gases': 0.23,
            'storage': 0.3,
            'pumped storage': 0.05,
        },
        'load_scale': 1.1, #55GW
        'generation_costs': {**DEFAULT_GEN_COSTS, 'natural gas': 180, 'coal': 150},
        'import_costs': {
            'Austria':     {'c1': 135, 'c2': 0.01},
            'Belgium':     {'c1': 132, 'c2': 0.01},
            'Switzerland': {'c1': 134, 'c2': 0.01}, 
            'Czechia':     {'c1': 134, 'c2': 0.01},
            'Denmark':     {'c1': 133, 'c2': 0.01}, 
            'France':      {'c1': 131, 'c2': 0.01}, 
            'Luxembourg':  {'c1': 134, 'c2': 0.01},
            'Netherlands': {'c1': 133, 'c2': 0.01},
            'Poland':      {'c1': 132, 'c2': 0.01}, 
            'Sweden':      {'c1': 32, 'c2': 0.01},  # Cheap
            'Norway':      {'c1': 40, 'c2': 0.01},  # Cheap
            'Germany':     {'c1': 134, 'c2': 0.01}, 
            'default':     {'c1': 70, 'c2': 0.01}
        }
    },

    # -------------------------------------------------------------------------
    # SCENARIO 3: WINTER STORM (North-South Congestion) 20251024
    # -------------------------------------------------------------------------
    'winter_storm': {
        'name': '3. Winter Storm ',
        'description': 'Max Wind in North. North neighbors CHEAP, South EXPENSIVE.',
        'capacity_factors': {
            'solar radiant energy': 0.04,
            'wind_onshore': 0.60,
            'biomass': 0.45,
            'wind_offshore': 0.68,
            'water': 0.27,
            'warmth': 0.05,
            'non-biogenic waste': 0.34,
            'hydrogen': 0.01,
            'natural gas': 0.09,
            'coal': 0.09,
            'brown coal': 0.17,
            'petroleum products': 0.00,
            'other gases': 0.00,
            'storage': 0.3,
            'pumped storage': 0.05,
        },
        'load_scale': 1.16, #57.8GW
        'generation_costs': DEFAULT_GEN_COSTS.copy(),
        'import_costs': {
            'Denmark':     {'c1': 38,   'c2': 0.01},  # Most country price crashed
            'Sweden':      {'c1': 37,  'c2': 0.01}, 
            'Norway':      {'c1': 38,  'c2': 0.01}, 
            'Netherlands': {'c1': 36,  'c2': 0.01}, 
            'Poland':      {'c1': 109,  'c2': 0.01},
            'Belgium':     {'c1': 35,  'c2': 0.01},
            'Luxembourg':  {'c1': 32,  'c2': 0.01},
            'France':      {'c1': 37,  'c2': 0.01},
            'Czechia':     {'c1': 97,  'c2': 0.01},
            'Austria':     {'c1': 98,  'c2': 0.01}, 
            'Switzerland': {'c1': 104,  'c2': 0.01}, 
            'Germany':     {'c1': 32,  'c2': 0.01},
            'default':     {'c1': 32,  'c2': 0.01}
        }
    },

    # -------------------------------------------------------------------------
    # SCENARIO 4: SUMMER PEAK PV (Voltage Issues) 20250614-13:00-14:00
    # -------------------------------------------------------------------------
    'summer_peak_pv': {
        'name': '4. Summer Voltage Stress',
        'description': 'High Solar, Low Load. Prices crash.',
        'capacity_factors': {
            'solar radiant energy': 0.43,
            'wind_onshore': 0.08,
            'biomass': 0.37,
            'wind_offshore': 0.16,
            'water': 0.02,
            'warmth': 0.05,
            'non-biogenic waste': 0.02,
            'hydrogen': 0.01,
            'natural gas': 0.05,
            'coal': 0.03,
            'brown coal': 0.17,
            'petroleum products': 0.17,
            'other gases': 0.04,
            'storage': 0.3,
            'pumped storage': 0.01,
        },
        'load_scale': 0.9, # originally 60GW, but here use less
        'generation_costs': DEFAULT_GEN_COSTS.copy(),
        'import_costs': {
            'Denmark':     {'c1': -19,   'c2': 0.01},  
            'Sweden':      {'c1': -19,  'c2': 0.01}, 
            'Norway':      {'c1': 2,  'c2': 0.01}, 
            'Netherlands': {'c1': -19,  'c2': 0.01}, 
            'Poland':      {'c1': -28,  'c2': 0.01},
            'Belgium':     {'c1': -17,  'c2': 0.01},
            'Luxembourg':  {'c1': -38,  'c2': 0.01},
            'France':      {'c1': -5,  'c2': 0.01},
            'Czechia':     {'c1': -36,  'c2': 0.01},
            'Austria':     {'c1': -51,  'c2': 0.01}, 
            'Switzerland': {'c1': -26,  'c2': 0.01}, 
            'Germany':     {'c1': -38,  'c2': 0.01},
            'default':     {'c1': -19,  'c2': 0.01}
        }
    },

    # -------------------------------------------------------------------------
    # SCENARIO 5: EVENING RAMP #20250605--19:00-20:00  unsure
    # -------------------------------------------------------------------------
    'evening_ramp': {
        'name': '5. Evening Ramp',
        'description': 'Sunset. Solar drops, Load peaks. Expensive flexibility needed.',
        'capacity_factors': {
            'solar radiant energy': 0.09,
            'wind_onshore': 0.16,
            'biomass': 0.46,
            'wind_offshore': 0.57,
            'water': 0.39,
            'warmth': 0.05,
            'non-biogenic waste': 0.02,
            'hydrogen': 0.01,
            'natural gas': 0.11,
            'coal': 0.18,
            'brown coal': 0.38,
            'petroleum products': 0.17,
            'other gases': 0.04,
            'storage': 0.3,
            'pumped storage': 0.07,
        },
        'load_scale': 1.15,
        'generation_costs': {**DEFAULT_GEN_COSTS, 'storage': 0},
        'import_costs': {
            'Denmark':     {'c1': 108,   'c2': 0.01},  
            'Sweden':      {'c1': 91,  'c2': 0.01}, 
            'Norway':      {'c1': 82,  'c2': 0.01}, 
            'Netherlands': {'c1': 95,  'c2': 0.01}, 
            'Poland':      {'c1': 122,  'c2': 0.01},
            'Belgium':     {'c1': 86,  'c2': 0.01},
            'Luxembourg':  {'c1': 108,  'c2': 0.01},
            'France':      {'c1': 15,  'c2': 0.01},
            'Czechia':     {'c1': 120,  'c2': 0.01},
            'Austria':     {'c1': 91,  'c2': 0.01}, 
            'Switzerland': {'c1': 100,  'c2': 0.01}, 
            'Germany':     {'c1': 108,  'c2': 0.01},
            'default':     {'c1': 108,  'c2': 0.01}
        }
    },

    # -------------------------------------------------------------------------
    # SCENARIO 6: TYPICAL WINTER 20250103
    # -------------------------------------------------------------------------
    'typical_winter': {
        'name': '6. Typical Winter Day',
        'description': 'January weekday. High Wind, low solar. Standard winter operation.', 
        'capacity_factors': {
            'solar radiant energy': 0.01,
            'wind_onshore': 0.42,
            'biomass': 0.44,
            'wind_offshore': 0.62,
            'water': 0.27,
            'warmth': 0.05,
            'non-biogenic waste': 0.05,
            'hydrogen': 0.01,
            'natural gas': 0.25,
            'coal': 0.28,
            'brown coal': 0.51,
            'petroleum products': 0.23,
            'other gases': 0.04,
            'storage': 0.3,
            'pumped storage': 0.02,
        },
        'load_scale': 1.05,
        'generation_costs': DEFAULT_GEN_COSTS.copy(),
        'import_costs': {
            'Denmark':     {'c1': 64,   'c2': 0.01},  
            'Sweden':      {'c1': 65,  'c2': 0.01}, 
            'Norway':      {'c1': 62,  'c2': 0.01}, 
            'Netherlands': {'c1': 114,  'c2': 0.01}, 
            'Poland':      {'c1': 87,  'c2': 0.01},
            'Belgium':     {'c1': 120,  'c2': 0.01},
            'Luxembourg':  {'c1': 90,  'c2': 0.01},
            'France':      {'c1': 115,  'c2': 0.01},
            'Czechia':     {'c1': 115,  'c2': 0.01},
            'Austria':     {'c1': 115,  'c2': 0.01}, 
            'Switzerland': {'c1': 125,  'c2': 0.01}, 
            'Germany':     {'c1': 90,  'c2': 0.01},
            'default':     {'c1': 90,  'c2': 0.01}
        }
    },

    # -------------------------------------------------------------------------
    # SCENARIO 7: TYPICAL SUMMER 20250729
    # -------------------------------------------------------------------------
    'typical_summer': {
        'name': '7. Typical Summer Day',
        'description': 'July weekday. Low prices, moderate load.',
        'capacity_factors': {
            'solar radiant energy': 0.12,
            'wind_onshore': 0.18,
            'biomass': 0.43,
            'wind_offshore': 0.71,
            'water': 0.42,
            'warmth': 0.00,
            'non-biogenic waste': 0.05,
            'hydrogen': 0.01,
            'natural gas': 0.08,
            'coal': 0.06,
            'brown coal': 0.36,
            'petroleum products': 0.23,
            'other gases': 0.04,
            'storage': 0.3,
            'pumped storage': 0.09,
        },
        'load_scale': 1.04,
        'generation_costs': DEFAULT_GEN_COSTS.copy(),
        'import_costs': {
            'Denmark':     {'c1': 58,   'c2': 0.01},  
            'Sweden':      {'c1': 13,  'c2': 0.01}, 
            'Norway':      {'c1': 63,  'c2': 0.01}, 
            'Netherlands': {'c1': 76,  'c2': 0.01}, 
            'Poland':      {'c1': 86,  'c2': 0.01},
            'Belgium':     {'c1': 74,  'c2': 0.01},
            'Luxembourg':  {'c1': 76,  'c2': 0.01},
            'France':      {'c1': 42,  'c2': 0.01},
            'Czechia':     {'c1': 79,  'c2': 0.01},
            'Austria':     {'c1': 80,  'c2': 0.01}, 
            'Switzerland': {'c1': 78,  'c2': 0.01}, 
            'Germany':     {'c1': 76,  'c2': 0.01},
            'default':     {'c1': 108,  'c2': 0.01}
        }
    },


    # -------------------------------------------------------------------------
    # SCENARIO 8: High Domes 20250729
    # -------------------------------------------------------------------------
    'high_domes': {
        'name': '8. High Domes Day',
        'description': 'Hign solar, high wind',
        'capacity_factors': {
            'solar radiant energy': 0.40,
            'wind_onshore': 0.20,
            'biomass': 0.21,
            'wind_offshore': 0.70,
            'water': 0.12,
            'warmth': 0.00,
            'non-biogenic waste': 0.05,
            'hydrogen': 0.01,
            'natural gas': 0.08,
            'coal': 0.06,
            'brown coal': 0.13,
            'petroleum products': 0.16,
            'other gases': 0.04,
            'storage': 0.3,
            'pumped storage': 0.01,
        },
        'load_scale': 1.15,
        'generation_costs': DEFAULT_GEN_COSTS.copy(),
        'import_costs': {
            'Denmark':     {'c1': 100,   'c2': 0.01},  
            'Sweden':      {'c1': 100,  'c2': 0.01}, 
            'Norway':      {'c1': 100,  'c2': 0.01}, 
            'Netherlands': {'c1': 100,  'c2': 0.01}, 
            'Poland':      {'c1': 100,  'c2': 0.01},
            'Belgium':     {'c1': 100,  'c2': 0.01},
            'Luxembourg':  {'c1': 100,  'c2': 0.01},
            'France':      {'c1': 100,  'c2': 0.01},
            'Czechia':     {'c1': 100,  'c2': 0.01},
            'Austria':     {'c1': 100,  'c2': 0.01}, 
            'Switzerland': {'c1': 100,  'c2': 0.01}, 
            'Germany':     {'c1': 30,  'c2': 0.01},
            'default':     {'c1': 40,  'c2': 0.01}
        }
    },
}