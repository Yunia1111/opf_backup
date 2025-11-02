# German Grid Power Flow Analysis

AC power flow calculation for the German transmission grid (380kV and 220kV) using pandapower.

## Overview

This module performs steady-state power flow analysis on the German grid model. It processes network topology data, applies generation/load balancing, and solves the AC power flow using Newton-Raphson method.

**Current Status**: Initial normal power flow implementation. Future work will extend to Optimal Power Flow (OPF).

## Requirements

```
pandas>=2.0.0
pandapower>=2.13.0
numpy>=1.24.0
folium>=0.14.0
```

Install dependencies:
```bash
pip install pandas pandapower numpy folium
```

## Project Structure

```
analysis/
├── main.py                          # Main workflow orchestrator
├── config.py                        # Configuration parameters, setup data file path
├── data_loader.py                   # CSV data loading
├── data_preprocessor.py             # Data preprocessing and balancing
├── external_grid_manager.py         # External grid (slack bus) setup
├── incremental_network_builder.py   # Network construction (380kV + 220kV)
├── power_flow_solver.py             # AC power flow solver
├── network_analyzer.py              # Post-convergence analysis
├── network_validity_checker.py      # Network validation
├── network_cleaner.py               # Network cleanup utilities
├── results_exporter.py              # Export results to CSV
├── visualizer.py                    # Interactive map visualization
└── readme.md                        # This file
```

## Input Data

The module expects CSV files in `analysis/data/intermediate_model/`:

- `buses.csv` - Network buses (substations)
- `connections.csv` - Transmission lines
- `generators.csv` - Generation units
- `loads.csv` - Load data
- `transformers.csv` - Transformer data
- `external_grids.csv` - Cross-border connections, manually created by Winnie side

## Usage

### Basic Usage

```bash
cd powerflow/analysis
python main.py
```

### Configuration

Edit `config.py` to adjust:

- **Generation scaling**: `GENERATION_SCALE_FACTOR` (default: 0.5)
- **Capacity factors**: `CAPACITY_FACTORS` for different generator types
- **Power flow algorithm**: `ALGORITHM_SEQUENCE` (default: Newton-Raphson)
- **Convergence tolerance**: `TOLERANCE_MVA` (default: 1e-5)

### Output

Results are saved to `results/`:

- `bus_results.csv` - Voltage magnitudes and angles
- `line_results.csv` - Line flows and loading
- `generator_results.csv` - Generator dispatch
- `network_map.html` - Interactive visualization

## Methodology

### 1. Data Loading and Preprocessing

- Merge parallel generator units by bus
- Apply capacity factors (wind, solar, etc.)
- Balance generation/load ratio to 1.15
- Group parallel transmission lines

### 2. Network Construction

- Build 380kV backbone network with PV generators
- Add 220kV network with PQ generators
- Configure external grids as slack buses
- Add transformers connecting voltage levels

### 3. Power Flow Calculation

- Newton-Raphson algorithm with fallback to Gauss-Seidel
- Automatic relaxation if convergence fails
- DC initialization as last resort

### 4. Results Analysis

- Voltage profile (per-unit values)
- Line loading (% of thermal limit)
- Transformer loading
- Cross-border power exchange
- Loss calculation

## Known Limitations

1. **DC Lines**: Currently viewed as AC lines
2. **Generation Control**: All 380kV generators are PV (voltage control), 220kV are PQ
3. **Load Model**: Static load (no voltage dependency)
4. **No OPF**: Current version solves only feasibility, not optimization

## Future Work

- [ ] Implement Optimal Power Flow (OPF)
- [ ] Add N-1 security constraints
- [ ] HVDC link modeling
- [ ] Dynamic load models
- [ ] Renewable uncertainty modeling

## Example Output

```
================================================================================
POWER FLOW RESULTS
================================================================================

📊 NETWORK STATISTICS:
   Buses:        2883
   Lines:        3270
   Transformers: 170
   Generators:   1768 PV + 2395 PQ
   Loads:        521

⚡ POWER BALANCE:
   Generation:   58152.8 MW
   Load:         50560.5 MW
   Losses:        400.5 MW (0.79%)

🔌 VOLTAGE PROFILE:
   Range:        0.9421 - 1.1346 pu
   Mean:         0.9950 pu

🌍 CROSS-BORDER POWER EXCHANGE:
   France          → xxx MW (Export)
   Netherlands     ← xxx MW (Import)
   Switzerland     → xxx MW (Export)
   ...

================================================================================
✓ Results saved to 'results/' directory
================================================================================
```

## Technical Details

### Generator Modeling

- **380kV**: PV generators (voltage control at 1.0 pu)
- **220kV**: PQ generators (active/reactive power specified)
- **External grids**: Slack buses (reference voltage and angle)

### Algorithm Parameters

- **Newton-Raphson**: Max 100 iterations, tolerance 1e-5 MVA
- **Fallback**: Gauss-Seidel with relaxed tolerance (1e-4 MVA)
- **DC init**: Linear approximation for difficult cases

### Coordinate System

- **Voltage levels**: 380kV (backbone), 220kV (regional)
- **Geographic**: WGS84 (lat/lon for visualization)
- **Per-unit base**: Network nominal voltage

Internal research use only. Not for public distribution.