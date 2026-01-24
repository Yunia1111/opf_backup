"""
Scenario Definitions
Designed to work with the "Generation Scenario Designer" HTML tool.
"""

# ==========================================
# 1. 基础配置 (Global Defaults & Constants)
# ==========================================

# 14种发电类型的基础配置 (作为兜底默认值)
BASE_CF = {
    'solar radiant energy': 0.07,
    'wind_onshore': 0.20,
    'wind_offshore': 0.37,
    'water': 0.37,
    'biomass': 0.55,
    'warmth': 0.19,
    'non-biogenic waste': 0.34,
    'natural gas': 0.15,
    'coal': 0.35,
    'brown coal': 0.45,
    'petroleum products': 0.12,
    'other gases': 0.10,
    'storage': 0.08,
    'hydrogen': 0.01,
    'pumped storage': 0.00 # 默认不作为发电机
}

DEFAULT_GEN_COSTS = {
    'solar radiant energy': 0, 'wind_onshore': 0, 'wind_offshore': 0, 
    'water': 0, 'biomass': 50, 'non-biogenic waste': 20, 'warmth': 20,
    'brown coal': 40, 'coal': 70, 'natural gas': 90, 'other gases': 90,
    'petroleum products': 100, 'hydrogen': 120, 'storage': 10,
    'default': 50
}

# --- 预设电价模板 (Price Templates) ---
# 供 create_scenario 的 price_template 参数使用
PRICES_STD = {
    'default':     {'c1': 70, 'c2': 0.01},
    'Germany':     {'c1': 70, 'c2': 0.01},
    'France':      {'c1': 65, 'c2': 0.01},
    'Denmark':     {'c1': 65, 'c2': 0.01},
    'Poland':      {'c1': 80, 'c2': 0.01},
    'Austria':     {'c1': 75, 'c2': 0.01},
    'Switzerland': {'c1': 80, 'c2': 0.01},
    'Czechia':     {'c1': 70, 'c2': 0.01},
    'Luxembourg':  {'c1': 70, 'c2': 0.01},
    'Netherlands': {'c1': 70, 'c2': 0.01},
    'Sweden':      {'c1': 50, 'c2': 0.01},
    'Norway':      {'c1': 50, 'c2': 0.01},
    'Belgium':     {'c1': 72, 'c2': 0.01}
}

# ==========================================
# 2. 场景创建函数 (Factory Function)
# ==========================================

def create_scenario(
    name, # [NEW] 显式传入直观的名称
    pv=0.0, 
    w_on=0.0, 
    w_off=0.0, 
    load=1.0, 
    cf_overrides={}, 
    price_template=PRICES_STD, 
    price_overrides={}
):
    """
    Args:
        name (str): Intuitive scenario name (e.g. 'pv_low_wind_low...')
        pv (float): Solar CF
        w_on (float): Onshore Wind CF
        w_off (float): Offshore Wind CF
        load (float): Load Scaling Factor
        cf_overrides (dict): Dictionary of CFs from the tool
        price_template (dict): Base price dictionary (PRICES_STD)
        price_overrides (dict): Specific country prices
    """
    
    # 1. Start with defaults
    cfs = BASE_CF.copy()
    
    # 2. Apply main variable CFs (ensure consistency)
    cfs['solar radiant energy'] = pv
    cfs['wind_onshore'] = w_on
    cfs['wind_offshore'] = w_off
    
    # 3. Apply detailed overrides from the tool
    cfs.update(cf_overrides)
    
    # 4. Handle Prices
    costs = price_template.copy()
    if price_overrides:
        costs.update(price_overrides)

    # 5. Auto-generate Description with Details
    desc_parts = [f"PV:{pv:.2f}", f"W_On:{w_on:.2f}", f"W_Off:{w_off:.2f}", f"Load:{load:.2f}"]
    
    if price_overrides:
        desc_parts.append(f"CustomPrices({len(price_overrides)})")
    
    description_str = " | ".join(desc_parts)

    return {
        'name': name, # 使用传入的直观名称
        'description': description_str, # 在描述中包含具体CF信息
        'load_scale': load,
        'capacity_factors': cfs,
        'generation_costs': DEFAULT_GEN_COSTS.copy(),
        'import_costs': costs,
        'storage_mode': 'bidirectional' # Default mode
    }

SCENARIOS = {}

# ==============================================================================
# 3. SCENARIO DEFINITIONS (27 Combinations)
# ==============================================================================
# 使用说明：
# 请将 HTML 工具生成的代码段直接粘贴覆盖下方的 create_scenario(...) 调用内容。
# 注意保留 name='...' 参数。
# ==============================================================================

# --- GROUP 1: PV LOW ----------------------------------------------------------

SCENARIOS['1.pv_low_wind_low_load_low'] = create_scenario(
    name='1.pv_low_wind_low_load_low',#reference day 14/07/2025 2-3 am
    pv=0.00, w_on=0.02, w_off=0.13, load=0.75,
    # Actual Load: 37,422.95 MWh (Scale: 0.75)
    # Renewable generation: 7,692 MWh
    # Conventional generation: 20,032.25 MWh
    cf_overrides={
        'solar radiant energy': 0.0005,
        'wind_onshore': 0.0236,
        'biomass': 0.4028,
        'wind_offshore': 0.1299,
        'water': 0.2566,
        'warmth': 0.0401,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0100,
        'natural gas': 0.1386,
        'coal': 0.2431,
        'brown coal': 0.6220,
        'petroleum products': 0.1200,
        'other gases': 0.0000,
        'storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 98.17, 'c2': 0.01},
        'Denmark': {'c1': 98.16, 'c2': 0.01},
        'France': {'c1': 49.28, 'c2': 0.01},
        'Luxembourg': {'c1': 98.17, 'c2': 0.01},
        'Netherlands': {'c1': 98.17, 'c2': 0.01},
        'Austria': {'c1': 94.01, 'c2': 0.01},
        'Poland': {'c1': 97.53, 'c2': 0.01},
        'Sweden': {'c1': 27.06, 'c2': 0.01},
        'Switzerland': {'c1': 99.07, 'c2': 0.01},
        'Czechia': {'c1': 97.31, 'c2': 0.01},
        'Norway': {'c1': 77, 'c2': 0.01},
        'Belgium': {'c1': 83.03, 'c2': 0.01},
    }
)

SCENARIOS['2.pv_low_wind_low_load_avg'] = create_scenario(
    name='2.pv_low_wind_low_load_avg', # Wednesday, 15/01/2025 22-23 pm
        pv=0.00, w_on=0.02, w_off=0.21, load=1.16,
    # Actual Load: 57,845.25 MWh (Scale: 1.16)
    # Renewable generation: 9,094.25 MWh
    # Conventional generation: 35,674.5 MWh
    cf_overrides={
        'solar radiant energy': 0.0001,
        'wind_onshore': 0.0220,
        'biomass': 0.4696,
        'wind_offshore': 0.2062,
        'water': 0.3308,
        'warmth': 0.0596,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0100,
        'natural gas': 0.4587,
        'coal': 0.3850,
        'brown coal': 0.7067,
        'petroleum products': 0.2364,
        'other gases': 0.0000,
        'storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 141.16, 'c2': 0.01},
        'Denmark': {'c1': 138.42, 'c2': 0.01},
        'France': {'c1': 138.77, 'c2': 0.01},
        'Luxembourg': {'c1': 141.16, 'c2': 0.01},
        'Netherlands': {'c1': 140.85, 'c2': 0.01},
        'Austria': {'c1': 139.81, 'c2': 0.01},
        'Poland': {'c1': 127.57, 'c2': 0.01},
        'Sweden': {'c1': 10.01, 'c2': 0.01},
        'Switzerland': {'c1': 141.54, 'c2': 0.01},
        'Czechia': {'c1': 140.72, 'c2': 0.01},
        'Norway': {'c1': 36.9, 'c2': 0.01},
        'Belgium': {'c1': 139.67, 'c2': 0.01},
    }
)

SCENARIOS['3.pv_low_wind_low_load_high'] = create_scenario(
    name='3.pv_low_wind_low_load_high', # Thursday 16/01/2025 17-18 pm
    pv=0.00, w_on=0.08, w_off=0.63, load=1.44,
    # Actual Load: 72,064.75 MWh (Scale: 1.44)
    # Renewable generation: 16,935 MWh
    # Conventional generation: 40,065 MWh
    cf_overrides={
        'solar radiant energy': 0.0001,
        'wind_onshore': 0.0792,
        'biomass': 0.5368,
        'wind_offshore': 0.6282,
        'water': 0.4299,
        'warmth': 0.0586,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0100,
        'natural gas': 0.5084,
        'coal': 0.3084,
        'brown coal': 0.7252,
        'petroleum products': 0.2522,
        'other gases': 0.0000,
        'storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 191.56, 'c2': 0.01},
        'Denmark': {'c1': 172.6, 'c2': 0.01},
        'France': {'c1': 164.77, 'c2': 0.01},
        'Luxembourg': {'c1': 191.56, 'c2': 0.01},
        'Netherlands': {'c1': 187.35, 'c2': 0.01},
        'Austria': {'c1': 190.42, 'c2': 0.01},
        'Poland': {'c1': 168.91, 'c2': 0.01},
        'Sweden': {'c1': 53.18, 'c2': 0.01},
        'Switzerland': {'c1': 207.02, 'c2': 0.01},
        'Czechia': {'c1': 187.68, 'c2': 0.01},
        'Norway': {'c1': 54.95, 'c2': 0.01},
        'Belgium': {'c1': 174.6, 'c2': 0.01},
    }
)

SCENARIOS['4.pv_low_wind_avg_load_low'] = create_scenario(
    name='4.pv_low_wind_avg_load_low',  # Sunday, November 24rd 2025 0-1 am
    pv=0.00, w_on=0.31, w_off=0.90, load=0.99,
    # Actual Load: 49,639.55 MWh (Scale: 0.99)
    # Renewable generation: 32,431.33 MWh
    # Conventional generation: 18,164.97 MWh
    cf_overrides={
        'solar radiant energy': 0.0000,
        'wind_onshore': 0.3149,
        'biomass': 0.4275,
        'wind_offshore': 0.8958,
        'water': 0.1823,
        'warmth': 0.0410,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.1931,
        'coal': 0.1523,
        'brown coal': 0.4560,
        'petroleum products': 0.2520,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 72.46, 'c2': 0.01},
        'Denmark': {'c1': 67.6, 'c2': 0.01},
        'France': {'c1': 66.78, 'c2': 0.01},
        'Luxembourg': {'c1': 72.46, 'c2': 0.01},
        'Netherlands': {'c1': 71.76, 'c2': 0.01},
        'Austria': {'c1': 75.75, 'c2': 0.01},
        'Poland': {'c1': 106.01, 'c2': 0.01},
        'Sweden': {'c1': 67.6, 'c2': 0.01},
        'Switzerland': {'c1': 102.39, 'c2': 0.01},
        'Czechia': {'c1': 79.57, 'c2': 0.01},
        'Norway': {'c1': 67.6, 'c2': 0.01},
        'Belgium': {'c1': 71.34, 'c2': 0.01},
    }
)

SCENARIOS['5.pv_low_wind_avg_load_avg'] = create_scenario(
    name='5.pv_low_wind_avg_load_avg', # Tuesday November 18th 2025 9-10 pm
    pv=0.00, w_on=0.31, w_off=0.12, load=1.22,
    # Actual Load: 61,092.55 MWh (Scale: 1.22)
    # Renewable generation: 28,046.69 MWh
    # Conventional generation: 31,105.55 MWh
    cf_overrides={
        'solar radiant energy': 0.0000,
        'wind_onshore': 0.3139,
        'biomass': 0.4878,
        'wind_offshore': 0.1196,
        'water': 0.2215,
        'warmth': 0.0410,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.3462,
        'coal': 0.3399,
        'brown coal': 0.7228,
        'petroleum products': 0.2519,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 94.64, 'c2': 0.01},
        'Denmark': {'c1': 97.05, 'c2': 0.01},
        'France': {'c1': 90.2, 'c2': 0.01},
        'Luxembourg': {'c1': 94.64, 'c2': 0.01},
        'Netherlands': {'c1': 93.8, 'c2': 0.01},
        'Austria': {'c1': 120.34, 'c2': 0.01},
        'Poland': {'c1': 104.39, 'c2': 0.01},
        'Sweden': {'c1': 97.05, 'c2': 0.01},
        'Switzerland': {'c1': 119, 'c2': 0.01},
        'Czechia': {'c1': 98.36, 'c2': 0.01},
        'Norway': {'c1': 91.96, 'c2': 0.01},
        'Belgium': {'c1': 93.56, 'c2': 0.01},
    }
)

SCENARIOS['6.pv_low_wind_avg_load_high'] = create_scenario(
    name='6.pv_low_wind_avg_load_high', # Wednesday 08/01/2025 17-18 pm
    pv=0.00, w_on=0.29, w_off=0.76, load=1.46,
    # Actual Load: 73,128.75 MWh (Scale: 1.46)
    # Renewable generation: 31,389.25 MWh
    # Conventional generation: 35,684.5 MWh
    cf_overrides={
        'solar radiant energy': 0.0002,
        'wind_onshore': 0.2859,
        'biomass': 0.5169,
        'wind_offshore': 0.7567,
        'water': 0.3610,
        'warmth': 0.0580,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0100,
        'natural gas': 0.3387,
        'coal': 0.4411,
        'brown coal': 0.7023,
        'petroleum products': 0.2103,
        'other gases': 0.0000,
        'storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 155.46, 'c2': 0.01},
        'Denmark': {'c1': 153.42, 'c2': 0.01},
        'France': {'c1': 124.58, 'c2': 0.01},
        'Luxembourg': {'c1': 155.46, 'c2': 0.01},
        'Netherlands': {'c1': 157.35, 'c2': 0.01},
        'Austria': {'c1': 154.4, 'c2': 0.01},
        'Poland': {'c1': 154.57, 'c2': 0.01},
        'Sweden': {'c1': 152.54, 'c2': 0.01},
        'Switzerland': {'c1': 146.57, 'c2': 0.01},
        'Czechia': {'c1': 153.96, 'c2': 0.01},
        'Norway': {'c1': 146.34, 'c2': 0.01},
        'Belgium': {'c1': 153.67, 'c2': 0.01},
    }
)

SCENARIOS['7.pv_low_wind_high_load_low'] = create_scenario(
    name='7.pv_low_wind_high_load_low', # Thursday 07/01/2025 2-3 am
    pv=0.00, w_on=0.56, w_off=0.53, load=0.93,
    # Actual Load: 46,711.5 MWh (Scale: 0.93)
    # Renewable generation: 46,957.25 MWh
    # Conventional generation: 10,923.5 MWh
    cf_overrides={
        'solar radiant energy': 0.0001,
        'wind_onshore': 0.5557,
        'biomass': 0.4007,
        'wind_offshore': 0.5281,
        'water': 0.3002,
        'warmth': 0.0570,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0100,
        'natural gas': 0.1092,
        'coal': 0.1189,
        'brown coal': 0.2422,
        'petroleum products': 0.2050,
        'other gases': 0.0000,
        'storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 8.9, 'c2': 0.01},
        'Denmark': {'c1': 5.3, 'c2': 0.01},
        'France': {'c1': 12.54, 'c2': 0.01},
        'Luxembourg': {'c1': 8.9, 'c2': 0.01},
        'Netherlands': {'c1': 8.9, 'c2': 0.01},
        'Austria': {'c1': 43.36, 'c2': 0.01},
        'Poland': {'c1': 26.12, 'c2': 0.01},
        'Sweden': {'c1': 5.33, 'c2': 0.01},
        'Switzerland': {'c1': 115.86, 'c2': 0.01},
        'Czechia': {'c1': 65.24, 'c2': 0.01},
        'Norway': {'c1': 20.37, 'c2': 0.01},
        'Belgium': {'c1': 10.4, 'c2': 0.01},
    }
)

SCENARIOS['8.pv_low_wind_high_load_avg'] = create_scenario(
    name='8.pv_low_wind_high_load_avg', # Tuesday 07/01/2025 21-22 pm
    pv=0.00, w_on=0.54, w_off=0.50, load=1.24,
    # Actual Load: 62,170.75 MWh (Scale: 1.24)
    # Renewable generation: 46,006 MWh
    # Conventional generation: 20,969.25 MWh
    cf_overrides={
        'solar radiant energy': 0.0001,
        'wind_onshore': 0.5350,
        'biomass': 0.4635,
        'wind_offshore': 0.5009,
        'water': 0.3124,
        'warmth': 0.0570,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0100,
        'natural gas': 0.2123,
        'coal': 0.2954,
        'brown coal': 0.4245,
        'petroleum products': 0.2057,
        'other gases': 0.0000,
        'storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 72.45, 'c2': 0.01},
        'Denmark': {'c1': 22.43, 'c2': 0.01},
        'France': {'c1': 100.55, 'c2': 0.01},
        'Luxembourg': {'c1': 72.45, 'c2': 0.01},
        'Netherlands': {'c1': 97.6, 'c2': 0.01},
        'Austria': {'c1': 111.66, 'c2': 0.01},
        'Poland': {'c1': 82.88, 'c2': 0.01},
        'Sweden': {'c1': 6.2, 'c2': 0.01},
        'Switzerland': {'c1': 131.9, 'c2': 0.01},
        'Czechia': {'c1': 108.87, 'c2': 0.01},
        'Norway': {'c1': 33.66, 'c2': 0.01},
        'Belgium': {'c1': 105.7, 'c2': 0.01},
    }
)

SCENARIOS['9.pv_low_wind_high_load_high'] = create_scenario(
    name='9.pv_low_wind_high_load_high', # Thursday 07/01/2025 18-19 pm
    pv=0.00, w_on=0.54, w_off=0.50, load=1.24,
    # Actual Load: 62,170.75 MWh (Scale: 1.24)
    # Renewable generation: 46,006 MWh
    # Conventional generation: 20,969.25 MWh
    cf_overrides={
        'solar radiant energy': 0.0001,
        'wind_onshore': 0.5350,
        'biomass': 0.4635,
        'wind_offshore': 0.5009,
        'water': 0.3124,
        'warmth': 0.0570,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0100,
        'natural gas': 0.2123,
        'coal': 0.2954,
        'brown coal': 0.4245,
        'petroleum products': 0.2057,
        'other gases': 0.0000,
        'storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 101.11, 'c2': 0.01},
        'Denmark': {'c1': 35.01, 'c2': 0.01},
        'France': {'c1': 128.87, 'c2': 0.01},
        'Luxembourg': {'c1': 101.11, 'c2': 0.01},
        'Netherlands': {'c1': 173.86, 'c2': 0.01},
        'Austria': {'c1': 135.56, 'c2': 0.01},
        'Poland': {'c1': 113.29, 'c2': 0.01},
        'Sweden': {'c1': 34.98, 'c2': 0.01},
        'Switzerland': {'c1': 142.06, 'c2': 0.01},
        'Czechia': {'c1': 140, 'c2': 0.01},
        'Norway': {'c1': 34.93, 'c2': 0.01},
        'Belgium': {'c1': 140, 'c2': 0.01},
    }
)

# --- GROUP 2: PV AVG ----------------------------------------------------------

SCENARIOS['10.pv_avg_wind_low_load_low'] = create_scenario(
    name='10.pv_avg_wind_low_load_low', # Sunday 02/03/2025 3-4 pm
    pv=0.22, w_on=0.09, w_off=0.57, load=0.96,
    # Actual Load: 48,314.77 MWh (Scale: 0.96)
    # Renewable generation: 38,652.5 MWh
    # Conventional generation: 13,729.5 MWh
    cf_overrides={
        'solar radiant energy': 0.2178,
        'wind_onshore': 0.0919,
        'biomass': 0.4392,
        'wind_offshore': 0.5658,
        'water': 0.2653,
        'warmth': 0.0547,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0100,
        'natural gas': 0.1033,
        'coal': 0.1166,
        'brown coal': 0.4311,
        'petroleum products': 0.2620,
        'other gases': 0.0000,
        'storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 50.73, 'c2': 0.01},
        'Denmark': {'c1': 19, 'c2': 0.01},
        'France': {'c1': 51.9, 'c2': 0.01},
        'Luxembourg': {'c1': 50.73, 'c2': 0.01},
        'Netherlands': {'c1': 50.7, 'c2': 0.01},
        'Austria': {'c1': 78.43, 'c2': 0.01},
        'Poland': {'c1': 59.37, 'c2': 0.01},
        'Sweden': {'c1': 1.91, 'c2': 0.01},
        'Switzerland': {'c1': 81.08, 'c2': 0.01},
        'Czechia': {'c1': 57.89, 'c2': 0.01},
        'Norway': {'c1': 35.88, 'c2': 0.01},
        'Belgium': {'c1': 50.97, 'c2': 0.01},
    }
)

SCENARIOS['11.pv_avg_wind_low_load_avg'] = create_scenario(
    name='11.pv_avg_wind_low_load_avg',# Wednesday March 5th 2025 15-16 pm
    pv=0.24, w_on=0.17, w_off=0.87, load=1.21,
    # Actual Load: 60,686.44 MWh (Scale: 1.21)
    # Renewable generation: 48,264.5 MWh
    # Conventional generation: 15,855 MWh
    cf_overrides={
        'solar radiant energy': 0.2434,
        'wind_onshore': 0.1659,
        'biomass': 0.4352,
        'wind_offshore': 0.8693,
        'water': 0.2466,
        'warmth': 0.0502,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.1388,
        'coal': 0.1934,
        'brown coal': 0.4037,
        'petroleum products': 0.1841,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 48.5, 'c2': 0.01},
        'Denmark': {'c1': 3.97, 'c2': 0.01},
        'France': {'c1': 50.53, 'c2': 0.01},
        'Luxembourg': {'c1': 48.5, 'c2': 0.01},
        'Netherlands': {'c1': 48.38, 'c2': 0.01},
        'Austria': {'c1': 87.8, 'c2': 0.01},
        'Poland': {'c1': 26.59, 'c2': 0.01},
        'Sweden': {'c1': 1.19, 'c2': 0.01},
        'Switzerland': {'c1': 114.66, 'c2': 0.01},
        'Czechia': {'c1': 68.05, 'c2': 0.01},
        'Norway': {'c1': 25.09, 'c2': 0.01},
        'Belgium': {'c1': 49.02, 'c2': 0.01},
    }
)

SCENARIOS['12.pv_avg_wind_low_load_high'] = create_scenario(
    name='12.pv_avg_wind_low_load_high', # Thursday 27/02/2025 11 am -12 pm
        pv=0.16, w_on=0.09, w_off=0.15, load=1.35,
    # Actual Load: 67,623.01 MWh (Scale: 1.35)
    # Renewable generation: 29,564.25 MWh
    # Conventional generation: 32,322.25 MWh
    cf_overrides={
        'solar radiant energy': 0.1558,
        'wind_onshore': 0.0923,
        'biomass': 0.4430,
        'wind_offshore': 0.1529,
        'water': 0.2862,
        'warmth': 0.0573,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0100,
        'natural gas': 0.3627,
        'coal': 0.3463,
        'brown coal': 0.7728,
        'petroleum products': 0.2245,
        'other gases': 0.0000,
        'storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 110, 'c2': 0.01},
        'Denmark': {'c1': 110.01, 'c2': 0.01},
        'France': {'c1': 100.19, 'c2': 0.01},
        'Luxembourg': {'c1': 110, 'c2': 0.01},
        'Netherlands': {'c1': 108.12, 'c2': 0.01},
        'Austria': {'c1': 118.15, 'c2': 0.01},
        'Poland': {'c1': 108.67, 'c2': 0.01},
        'Sweden': {'c1': 98.4, 'c2': 0.01},
        'Switzerland': {'c1': 124.51, 'c2': 0.01},
        'Czechia': {'c1': 103.97, 'c2': 0.01},
        'Norway': {'c1': 104.71, 'c2': 0.01},
        'Belgium': {'c1': 107.27, 'c2': 0.01},
    }
)

SCENARIOS['13.pv_avg_wind_avg_load_low'] = create_scenario(
    name='13.pv_avg_wind_avg_load_low', # Saturday 05/04/2025
        pv=0.17, w_on=0.27, w_off=0.36, load=0.95,
    # Actual Load: 47,323.82 MWh (Scale: 0.95)
    # Renewable generation: 43,839.5 MWh
    # Conventional generation: 7,045.25 MWh
    cf_overrides={
        'solar radiant energy': 0.1662,
        'wind_onshore': 0.2744,
        'biomass': 0.4068,
        'wind_offshore': 0.3617,
        'water': 0.2281,
        'warmth': 0.0477,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0100,
        'natural gas': 0.0616,
        'coal': 0.0485,
        'brown coal': 0.1761,
        'petroleum products': 0.2155,
        'other gases': 0.0000,
        'storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Denmark': {'c1': 3.95, 'c2': 0.01},
        'France': {'c1': 0.1, 'c2': 0.01},
        'Netherlands': {'c1': 0.27, 'c2': 0.01},
        'Austria': {'c1': 0.1, 'c2': 0.01},
        'Poland': {'c1': 18.2, 'c2': 0.01},
        'Sweden': {'c1': 4.04, 'c2': 0.01},
        'Switzerland': {'c1': 12.03, 'c2': 0.01},
        'Czechia': {'c1': 5.16, 'c2': 0.01},
        'Norway': {'c1': 45.3, 'c2': 0.01},
        'Belgium': {'c1': 0.15, 'c2': 0.01},
    }
)

SCENARIOS['14.pv_avg_wind_avg_load_avg'] = create_scenario(
    name='14.pv_avg_wind_avg_load_avg', # Monday May 26th 2025 17-18 pm
    pv=0.19, w_on=0.24, w_off=0.54, load=1.10,
    # Actual Load: 55,072.61 MWh (Scale: 1.10)
    # Renewable generation: 45,068.25 MWh
    # Conventional generation: 9,431.25 MWh
    cf_overrides={
        'solar radiant energy': 0.1859,
        'wind_onshore': 0.2401,
        'biomass': 0.4146,
        'wind_offshore': 0.5371,
        'water': 0.2798,
        'warmth': 0.0447,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.0825,
        'coal': 0.0621,
        'brown coal': 0.2458,
        'petroleum products': 0.2217,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 17.65, 'c2': 0.01},
        'Denmark': {'c1': 37.2, 'c2': 0.01},
        'France': {'c1': 14.78, 'c2': 0.01},
        'Luxembourg': {'c1': 17.65, 'c2': 0.01},
        'Netherlands': {'c1': 15.1, 'c2': 0.01},
        'Austria': {'c1': 61.05, 'c2': 0.01},
        'Poland': {'c1': 112.08, 'c2': 0.01},
        'Sweden': {'c1': 33.5, 'c2': 0.01},
        'Switzerland': {'c1': 85, 'c2': 0.01},
        'Czechia': {'c1': 57.95, 'c2': 0.01},
        'Norway': {'c1': 55.48, 'c2': 0.01},
        'Belgium': {'c1': 15.68, 'c2': 0.01},
    }
)

SCENARIOS['15.pv_avg_wind_avg_load_high'] = create_scenario(
    name='15.pv_avg_wind_avg_load_high', # Wednesday 05/11/2025 9-10 am
        pv=0.18, w_on=0.23, w_off=0.84, load=1.36,
    # Actual Load: 68,247 MWh (Scale: 1.36)
    # Renewable generation: 46,473.12 MWh
    # Conventional generation: 18,134.87 MWh
    cf_overrides={
        'solar radiant energy': 0.1773,
        'wind_onshore': 0.2348,
        'biomass': 0.4877,
        'wind_offshore': 0.8411,
        'water': 0.2848,
        'warmth': 0.0396,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.1637,
        'coal': 0.1769,
        'brown coal': 0.4875,
        'petroleum products': 0.2663,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 74.54, 'c2': 0.01},
        'Denmark': {'c1': 74.23, 'c2': 0.01},
        'France': {'c1': 21.28, 'c2': 0.01},
        'Luxembourg': {'c1': 74.54, 'c2': 0.01},
        'Netherlands': {'c1': 100.7, 'c2': 0.01},
        'Austria': {'c1': 100.39, 'c2': 0.01},
        'Poland': {'c1': 90.87, 'c2': 0.01},
        'Sweden': {'c1': 38.27, 'c2': 0.01},
        'Switzerland': {'c1': 112.4, 'c2': 0.01},
        'Czechia': {'c1': 93.57, 'c2': 0.01},
        'Norway': {'c1': 65.2, 'c2': 0.01},
        'Belgium': {'c1': 69.65, 'c2': 0.01},
    }
)

SCENARIOS['16.pv_avg_wind_high_load_low'] = create_scenario(
    name='16.pv_avg_wind_high_load_low', # Sunday Oct 5th 2025 14-15 pm, change load
    pv=0.16, w_on=0.48, w_off=0.49, load=1.18,
    # Actual Load: 59,087.32 (Origin:49,348.23 MWh (Scale: 0.99))
    # Renewable generation: 58,044.13 MWh
    # Conventional generation: 5,908.75 MWh
    cf_overrides={
        'solar radiant energy': 0.1552,
        'wind_onshore': 0.4840,
        'biomass': 0.3868,
        'wind_offshore': 0.4916,
        'water': 0.2952,
        'warmth': 0.0373,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.0552,
        'coal': 0.0322,
        'brown coal': 0.1337,
        'petroleum products': 0.2191,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 2.94, 'c2': 0.01},
        'Denmark': {'c1': 0.97, 'c2': 0.01},
        'France': {'c1': 2.45, 'c2': 0.01},
        'Luxembourg': {'c1': 2.94, 'c2': 0.01},
        'Netherlands': {'c1': 2.85, 'c2': 0.01},
        'Austria': {'c1': 0.74, 'c2': 0.01},
        'Poland': {'c1': 2.68, 'c2': 0.01},
        'Sweden': {'c1': 1.49, 'c2': 0.01},
        'Switzerland': {'c1': 7, 'c2': 0.01},
        'Czechia': {'c1': 1.62, 'c2': 0.01},
        'Norway': {'c1': 1.96, 'c2': 0.01},
        'Belgium': {'c1': 2.7, 'c2': 0.01},
    }
)

SCENARIOS['17.pv_avg_wind_high_load_avg'] = create_scenario(
    name='17.pv_avg_wind_high_load_avg',# Monday 20/10/2025 11-12 pm
    pv=0.15, w_on=0.28, w_off=1.00, load=1.35,
    # Actual Load: 67,532.52 MWh (Scale: 1.35)
    # Renewable generation: 46,585.28 MWh
    # Conventional generation: 16,880.64 MWh
    cf_overrides={
        'solar radiant energy': 0.1463,
        'wind_onshore': 0.2777,
        'biomass': 0.4232,
        'wind_offshore': 1.0000,
        'water': 0.2603,
        'warmth': 0.0473,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.1488,
        'coal': 0.1888,
        'brown coal': 0.4218,
        'petroleum products': 0.2441,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 69.94, 'c2': 0.01},
        'Denmark': {'c1': 66.54, 'c2': 0.01},
        'France': {'c1': 16.68, 'c2': 0.01},
        'Luxembourg': {'c1': 69.94, 'c2': 0.01},
        'Netherlands': {'c1': 68.91, 'c2': 0.01},
        'Austria': {'c1': 81.15, 'c2': 0.01},
        'Poland': {'c1': 54.49, 'c2': 0.01},
        'Sweden': {'c1': 61.51, 'c2': 0.01},
        'Switzerland': {'c1': 120.25, 'c2': 0.01},
        'Czechia': {'c1': 84.44, 'c2': 0.01},
        'Norway': {'c1': 61.56, 'c2': 0.01},
        'Belgium': {'c1': 57.88, 'c2': 0.01},
    }
)

SCENARIOS['18.pv_avg_wind_high_load_high'] = create_scenario(
    name='18.pv_avg_wind_high_load_high', # Monday, October 27th, 2025 12-13 pm
    pv=0.11, w_on=0.45, w_off=0.93, load=1.32,
    # Actual Load: 66,180.32 MWh (Scale: 1.32)
    # Renewable generation: 54,508.42 MWh
    # Conventional generation: 11,901.96 MWh
    cf_overrides={
        'solar radiant energy': 0.1096,
        'wind_onshore': 0.4537,
        'biomass': 0.4352,
        'wind_offshore': 0.9275,
        'water': 0.3070,
        'warmth': 0.0463,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.1609,
        'coal': 0.1063,
        'brown coal': 0.1840,
        'petroleum products': 0.2039,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 81.12, 'c2': 0.01},
        'Denmark': {'c1': 81.12, 'c2': 0.01},
        'France': {'c1': 21.77, 'c2': 0.01},
        'Luxembourg': {'c1': 81.12, 'c2': 0.01},
        'Netherlands': {'c1': 70, 'c2': 0.01},
        'Austria': {'c1': 113.86, 'c2': 0.01},
        'Poland': {'c1': 98.49, 'c2': 0.01},
        'Sweden': {'c1': 80.93, 'c2': 0.01},
        'Switzerland': {'c1': 99.61, 'c2': 0.01},
        'Czechia': {'c1': 98.55, 'c2': 0.01},
        'Norway': {'c1': 72.18, 'c2': 0.01},
        'Belgium': {'c1': 62.23, 'c2': 0.01},
    }
)

# --- GROUP 3: PV HIGH ---------------------------------------------------------

SCENARIOS['19.pv_high_wind_low_load_low'] = create_scenario(
    name='19.pv_high_wind_low_load_low', # Sunday, July 13th, 2025, 11am -12 pm
    pv=0.30, w_on=0.04, w_off=0.25, load=0.93,
    # Actual Load: 46,423.64 MWh (Scale: 0.93)
    # Renewable generation: 41,690.96 MWh
    # Conventional generation: 6,921 MWh
    cf_overrides={
        'solar radiant energy': 0.3040,
        'wind_onshore': 0.0400,
        'biomass': 0.3744,
        'wind_offshore': 0.2473,
        'water': 0.2984,
        'warmth': 0.0383,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.0437,
        'coal': 0.0317,
        'brown coal': 0.2191,
        'petroleum products': 0.2152,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 0.05, 'c2': 0.01},
        'Denmark': {'c1': 3.48, 'c2': 0.01},
        'France': {'c1': 0.05, 'c2': 0.01},
        'Luxembourg': {'c1': 0.05, 'c2': 0.01},
        'Netherlands': {'c1': 0.05, 'c2': 0.01},
        'Austria': {'c1': 0.05, 'c2': 0.01},
        'Poland': {'c1': 0.05, 'c2': 0.01},
        'Sweden': {'c1': 5.75, 'c2': 0.01},
        'Switzerland': {'c1': 9.42, 'c2': 0.01},
        'Czechia': {'c1': 0.05, 'c2': 0.01},
        'Norway': {'c1': 55.24, 'c2': 0.01},
        'Belgium': {'c1': 0.05, 'c2': 0.01},
    }
)

SCENARIOS['20.pv_high_wind_low_load_avg'] = create_scenario(
    name='20.pv_high_wind_low_load_avg',
    pv=0.42, w_on=0.09, w_off=0.36, load=1.13,
    # Actual Load: 56,493.05 MWh (Scale: 1.13)
    # Renewable generation: 57,541.91 MWh
    # Conventional generation: 7,958 MWh
    cf_overrides={
        'solar radiant energy': 0.4177,
        'wind_onshore': 0.0869,
        'biomass': 0.3686,
        'wind_offshore': 0.3643,
        'water': 0.2770,
        'warmth': 0.0367,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.0475,
        'coal': 0.0562,
        'brown coal': 0.2697,
        'petroleum products': 0.1780,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 1.56, 'c2': 0.01},
        'Denmark': {'c1': 1.74, 'c2': 0.01},
        'France': {'c1': 12.34, 'c2': 0.01},
        'Luxembourg': {'c1': 1.56, 'c2': 0.01},
        'Netherlands': {'c1': 1.56, 'c2': 0.01},
        'Austria': {'c1': 53.44, 'c2': 0.01},
        'Poland': {'c1': 22.99, 'c2': 0.01},
        'Sweden': {'c1': 1.58, 'c2': 0.01},
        'Switzerland': {'c1': 66.95, 'c2': 0.01},
        'Norway': {'c1': 13.56, 'c2': 0.01},
        'Belgium': {'c1': 10.31, 'c2': 0.01},
    }
)

SCENARIOS['21.pv_high_wind_low_load_high'] = create_scenario(
    name='21.pv_high_wind_low_load_high', # WednesdayJuly 2 11 am -12 pm
    pv=0.42, w_on=0.02, w_off=0.18, load=1.21,
    # Actual Load: 60,638.63 MWh (Scale: 1.21)
    # Renewable generation: 51,518.18 MWh
    # Conventional generation: 12,747 MWh
    cf_overrides={
        'solar radiant energy': 0.4160,
        'wind_onshore': 0.0219,
        'biomass': 0.3581,
        'wind_offshore': 0.1793,
        'water': 0.2659,
        'warmth': 0.0279,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.0956,
        'coal': 0.1363,
        'brown coal': 0.3882,
        'petroleum products': 0.1773,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 69.93, 'c2': 0.01},
        'Denmark': {'c1': 69.9, 'c2': 0.01},
        'France': {'c1': 76.39, 'c2': 0.01},
        'Luxembourg': {'c1': 69.93, 'c2': 0.01},
        'Netherlands': {'c1': 72.78, 'c2': 0.01},
        'Austria': {'c1': 62.03, 'c2': 0.01},
        'Poland': {'c1': 24.6, 'c2': 0.01},
        'Sweden': {'c1': 29.96, 'c2': 0.01},
        'Switzerland': {'c1': 77.69, 'c2': 0.01},
        'Czechia': {'c1': 80.01, 'c2': 0.01},
        'Norway': {'c1': 59.8, 'c2': 0.01},
        'Belgium': {'c1': 74.56, 'c2': 0.01},
    }
)

SCENARIOS['22.pv_high_wind_avg_load_low'] = create_scenario(
    name='22.pv_high_wind_avg_load_low', # Saturday, July 5 2025 13-14 pm, changed
    pv=0.37, w_on=0.20, w_off=0.32, load=1,
    # Actual Load: 46,950.58 MWh (Scale: 0.94)
    # Renewable generation: 59,144.88 MWh
    # Conventional generation: 6,580 MWh
    cf_overrides={
        'solar radiant energy': 0.34,  # 0.3656,
        'wind_onshore': 0.1951,
        'biomass': 0.3655,
        'wind_offshore': 0.3186,
        'water': 0.2836,
        'warmth': 0.0374,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.0454,
        'coal': 0.0318,
        'brown coal': 0.2172,
        'petroleum products': 0.1580,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 2.05, 'c2': 0.01},
        'Denmark': {'c1': 0.37, 'c2': 0.01},
        'France': {'c1': 0.1, 'c2': 0.01},
        'Luxembourg': {'c1': 2.05, 'c2': 0.01},
        'Netherlands': {'c1': 2, 'c2': 0.01},
        'Austria': {'c1': 6.52, 'c2': 0.01},
        'Poland': {'c1': 0.53, 'c2': 0.01},
        'Sweden': {'c1': 0.37, 'c2': 0.01},
        'Switzerland': {'c1': 2.08, 'c2': 0.01},
        'Czechia': {'c1': 1.77, 'c2': 0.01},
        'Norway': {'c1': 0.37, 'c2': 0.01},
        'Belgium': {'c1': 2.2, 'c2': 0.01},
    }
)

SCENARIOS['23.pv_high_wind_avg_load_avg'] = create_scenario(
    name='23.pv_high_wind_avg_load_avg', # Tuesday, July 8th, 3 -4 pm
    pv=0.26, w_on=0.19, w_off=0.35, load=1.13,
    # Actual Load: 56,429.43 MWh (Scale: 1.13)
    # Renewable generation: 48,569.6 MWh
    # Conventional generation: 10,895 MWh
    cf_overrides={
        'solar radiant energy': 0.2635,
        'wind_onshore': 0.1918,
        'biomass': 0.3750,
        'wind_offshore': 0.3468,
        'water': 0.3197,
        'warmth': 0.0406,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.0700,
        'coal': 0.1191,
        'brown coal': 0.3445,
        'petroleum products': 0.1669,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 54.65, 'c2': 0.01},
        'Denmark': {'c1': 48.31, 'c2': 0.01},
        'Luxembourg': {'c1': 54.65, 'c2': 0.01},
        'Netherlands': {'c1': 47.58, 'c2': 0.01},
        'Austria': {'c1': 76.98, 'c2': 0.01},
        'Poland': {'c1': 101.3, 'c2': 0.01},
        'Sweden': {'c1': 46.19, 'c2': 0.01},
        'Switzerland': {'c1': 91.7, 'c2': 0.01},
        'Czechia': {'c1': 74.34, 'c2': 0.01},
        'Norway': {'c1': 62.87, 'c2': 0.01},
        'Belgium': {'c1': 40.69, 'c2': 0.01},
    }
)

SCENARIOS['24.pv_high_wind_avg_load_high'] = create_scenario(
    name='24.pv_high_wind_avg_load_high', # Thursday, July 3rd, 2025 11 am -12 pm
    pv=0.28, w_on=0.21, w_off=0.27, load=1.28,
    # Actual Load: 64,026.38 MWh (Scale: 1.28)
    # Renewable generation: 50,770.84 MWh
    # Conventional generation: 12,493 MWh
    cf_overrides={
        'solar radiant energy': 0.2774,
        'wind_onshore': 0.2102,
        'biomass': 0.3801,
        'wind_offshore': 0.2711,
        'water': 0.3065,
        'warmth': 0.0339,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.0806,
        'coal': 0.1643,
        'brown coal': 0.3675,
        'petroleum products': 0.1901,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 57.35, 'c2': 0.01},
        'Denmark': {'c1': 4.15, 'c2': 0.01},
        'France': {'c1': 57.35, 'c2': 0.01},
        'Luxembourg': {'c1': 57.35, 'c2': 0.01},
        'Netherlands': {'c1': 57.35, 'c2': 0.01},
        'Austria': {'c1': 57.35, 'c2': 0.01},
        'Poland': {'c1': 57.35, 'c2': 0.01},
        'Sweden': {'c1': 3.3, 'c2': 0.01},
        'Switzerland': {'c1': 86.71, 'c2': 0.01},
        'Czechia': {'c1': 57.35, 'c2': 0.01},
        'Norway': {'c1': 54.99, 'c2': 0.01},
        'Belgium': {'c1': 57.35, 'c2': 0.01},
    }
)

SCENARIOS['25.pv_high_wind_high_load_low'] = create_scenario(
    name='25.pv_high_wind_high_load_low',  # June 23rd 2025 12 am -13 pm
    pv=0.29, w_on=0.43, w_off=0.35, load=1.24,
    # Actual Load: 61,933.07 MWh (Scale: 1.24)
    # Renewable generation: 67,470.5 MWh
    # Conventional generation: 6,804.5 MWh
    cf_overrides={
        'solar radiant energy': 0.2895,
        'wind_onshore': 0.4299,
        'biomass': 0.3654,
        'wind_offshore': 0.3478,
        'water': 0.3064,
        'warmth': 0.0358,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.0537,
        'coal': 0.0854,
        'brown coal': 0.1590,
        'petroleum products': 0.1768,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 12.76, 'c2': 0.01},
        'Denmark': {'c1': 0.95, 'c2': 0.01},
        'France': {'c1': 1.98, 'c2': 0.01},
        'Luxembourg': {'c1': 12.76, 'c2': 0.01},
        'Netherlands': {'c1': 9.9, 'c2': 0.01},
        'Austria': {'c1': 2.93, 'c2': 0.01},
        'Poland': {'c1': 10.42, 'c2': 0.01},
        'Sweden': {'c1': 0.95, 'c2': 0.01},
        'Switzerland': {'c1': 0.15, 'c2': 0.01},
        'Czechia': {'c1': 84.3, 'c2': 0.01},
        'Norway': {'c1': 0.95, 'c2': 0.01},
        'Belgium': {'c1': 6.68, 'c2': 0.01},
    }
)

SCENARIOS['26.pv_high_wind_high_load_avg'] = create_scenario(
    name='26.pv_high_wind_high_load_avg', # Monday June 23th, 2025 3-4 pm
    pv=0.26, w_on=0.45, w_off=0.10, load=1.18,
    # Actual Load: 58,951.51 MWh (Scale: 1.18)
    # Renewable generation: 63,824.5 MWh
    # Conventional generation: 7,872.5 MWh
    cf_overrides={
        'solar radiant energy': 0.2572,
        'wind_onshore': 0.4526,
        'biomass': 0.3636,
        'wind_offshore': 0.1046,
        'water': 0.2729,
        'warmth': 0.0363,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.0634,
        'coal': 0.1289,
        'brown coal': 0.1586,
        'petroleum products': 0.1739,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 32.69, 'c2': 0.01},
        'Denmark': {'c1': 0.46, 'c2': 0.01},
        'France': {'c1': 9.53, 'c2': 0.01},
        'Luxembourg': {'c1': 32.69, 'c2': 0.01},
        'Netherlands': {'c1': 32.69, 'c2': 0.01},
        'Austria': {'c1': 13.91, 'c2': 0.01},
        'Poland': {'c1': 9.5, 'c2': 0.01},
        'Sweden': {'c1': 0.46, 'c2': 0.01},
        'Switzerland': {'c1': 58.69, 'c2': 0.01},
        'Czechia': {'c1': 142.84, 'c2': 0.01},
        'Norway': {'c1': 0.37, 'c2': 0.01},
        'Belgium': {'c1': 25.72, 'c2': 0.01},
    }
)

SCENARIOS['27.pv_high_wind_high_load_high'] = create_scenario(
    name='27.pv_high_wind_high_load_high', #June 23rd, 2025 11 am -12 pm
    pv=0.29, w_on=0.41, w_off=0.29, load=1.25,
    # Actual Load: 62,778.7 MWh (Scale: 1.25)
    # Renewable generation: 66,096.25 MWh
    # Conventional generation: 6,951.5 MWh
    cf_overrides={
        'solar radiant energy': 0.2929,
        'wind_onshore': 0.4072,
        'biomass': 0.3739,
        'wind_offshore': 0.2920,
        'water': 0.3255,
        'warmth': 0.0359,
        'non-biogenic waste': 0.0000,
        'hydrogen': 0.0000,
        'natural gas': 0.0518,
        'coal': 0.0858,
        'brown coal': 0.1649,
        'petroleum products': 0.1778,
        'other gases': 0.0000,
        'storage': 0.0000,
        'pumped storage': 0.0000,
    },
    price_template=PRICES_STD,
    price_overrides={
        'Germany': {'c1': 6.11, 'c2': 0.01},
        'Denmark': {'c1': 2.19, 'c2': 0.01},
        'France': {'c1': 0.01, 'c2': 0.01},
        'Luxembourg': {'c1': 6.11, 'c2': 0.01},
        'Netherlands': {'c1': 4.48, 'c2': 0.01},
        'Austria': {'c1': 0.07, 'c2': 0.01},
        'Poland': {'c1': 5.9, 'c2': 0.01},
        'Sweden': {'c1': 2.19, 'c2': 0.01},
        'Switzerland': {'c1': 44.01, 'c2': 0.01},
        'Czechia': {'c1': 50.01, 'c2': 0.01},
        'Norway': {'c1': 2.68, 'c2': 0.01},
        'Belgium': {'c1': 2.7, 'c2': 0.01},
    }
)

# ==============================================================================
# 4. BATTERY SCENARIOS (Derived from Avg)
# ==============================================================================

# 使用 Avg Day 的配置，仅修改电池模式和名称
base_scen = SCENARIOS['14.pv_avg_wind_avg_load_avg']

# A. Charging
s_charge_low = base_scen.copy()
s_charge_low['name'] = 'avg_day_charge_low' # 直观名称
s_charge_low['storage_mode'] = 'charge_only'
s_charge_low['capacity_factors'] = base_scen['capacity_factors'].copy()
s_charge_low['capacity_factors']['storage'] = 0.20
s_charge_low['description'] += " | Mode: Charge Low" 
SCENARIOS['avg_day_charge_low'] = s_charge_low

s_charge_high = base_scen.copy()
s_charge_high['name'] = 'avg_day_charge_high'
s_charge_high['storage_mode'] = 'charge_only'
s_charge_high['capacity_factors'] = base_scen['capacity_factors'].copy()
s_charge_high['capacity_factors']['storage'] = 0.70
s_charge_high['description'] += " | Mode: Charge High"
SCENARIOS['avg_day_charge_high'] = s_charge_high

# B. Discharging
s_discharge_low = base_scen.copy()
s_discharge_low['name'] = 'avg_day_discharge_low'
s_discharge_low['storage_mode'] = 'discharge_only'
s_discharge_low['capacity_factors'] = base_scen['capacity_factors'].copy()
s_discharge_low['capacity_factors']['storage'] = 0.20
s_discharge_low['description'] += " | Mode: Discharge Low"
SCENARIOS['avg_day_discharge_low'] = s_discharge_low

s_discharge_high = base_scen.copy()
s_discharge_high['name'] = 'avg_day_discharge_high'
s_discharge_high['storage_mode'] = 'discharge_only'
s_discharge_high['capacity_factors'] = base_scen['capacity_factors'].copy()
s_discharge_high['capacity_factors']['storage'] = 0.70
s_discharge_high['description'] += " | Mode: Discharge High"
SCENARIOS['avg_day_discharge_high'] = s_discharge_high