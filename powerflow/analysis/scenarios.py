"""
Scenario Definitions - Contains fixed capacity factors (CFs) and load scaling.
"""

SCENARIOS = {
    'average_of_2024': {
        'name': 'Average Of 2024',
        'description': 'A mixed scenario using the average CF of 2024 for all gen_type',
        'capacity_factors': {
            'solar radiant energy': 0.07, 'wind_onshore': 0.20, 'biomass': 0.50,
            'wind_offshore': 0.37, 'water': 0.37, 'warmth': 0.19, 
            'non-biogenic waste': 0.34, 'hydrogen': 0.01, 'natural gas': 0.15,
            'coal': 0.35, 'brown coal': 0.55, 'petroleum products': 0.12,
            'other gases': 0.10, 
            'storage': 0.2,        
        },
        'load_scale': 1.00,
    },

    'high_wind_no_solar': {
        'name': 'High Wind No Solar',
        'description': 'High wind/no solar. Reduce traditional generation to compensate.',
        'capacity_factors': {
            'solar radiant energy': 0.00, 'wind_onshore': 0.38, 'biomass': 0.50,
            'wind_offshore': 0.45, 'water': 0.00, 'warmth': 0.19, 
            'non-biogenic waste': 0.34, 'hydrogen': 0.01, 'natural gas': 0.10,
            'coal': 0.30, 'brown coal': 0.40, 'petroleum products': 0.12,
            'other gases': 0.10, 
            'storage': 1.00,
        },
        'load_scale': 1.00,
    },

    'low_wind_high_solar': {
        'name': 'Low Wind High Solar',
        'description': 'Low wind/high solar. Renewables changes can compensate each other.',
        'capacity_factors': {
            'solar radiant energy': 0.15, 'wind_onshore': 0.10, 'biomass': 0.50,
            'wind_offshore': 0.20, 'water': 0.37, 'warmth': 0.19, 
            'non-biogenic waste': 0.40, 'hydrogen': 0.01, 'natural gas': 0.15,
            'coal': 0.35, 'brown coal': 0.45, 'petroleum products': 0.12,
            'other gases': 0.10, 
            'storage': 1.00,
        },
        'load_scale': 1.00,
    },

    'dunkelflaute': {
        'name': 'Dunkelflaute',
        'description': 'No sun, low wind - compensate by conventional generation.',
        'capacity_factors': {
            'solar radiant energy': 0.00, 'wind_onshore': 0.10, 'biomass': 0.50,
            'wind_offshore': 0.10, 'water': 0.45, 'warmth': 0.30,
            'non-biogenic waste': 0.34, 'hydrogen': 0.01, 'natural gas': 0.32,
            'coal': 0.68, 'brown coal': 0.71, 'petroleum products': 0.15,
            'other gases': 0.10, 
            'storage': 1.00,
        },
        'load_scale': 1.00,
    },

    'peak_load': {
        'name': 'Peak Load',
        'description': '1.3 times the load, compensate by all type of generation.',
        'capacity_factors': {
            'solar radiant energy': 0.10, 'wind_onshore': 0.26, 'biomass': 0.50,
            'wind_offshore': 0.40, 'water': 0.40, 'warmth': 0.19,
            'non-biogenic waste': 0.34, 'hydrogen': 0.01, 'natural gas': 0.18,
            'coal': 0.41, 'brown coal': 0.51, 'petroleum products': 0.15,
            'other gases': 0.10, 
            'storage': 1.00,
        },
        'load_scale': 1.30,
    }, 
}