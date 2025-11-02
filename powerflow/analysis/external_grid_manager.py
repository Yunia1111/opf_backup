"""
External grid manager - handles slack bus selection and configuration
"""
import pandas as pd
import numpy as np
import config

class ExternalGridManager:
    def __init__(self, buses, connections, external_grids_df=None):
        self.buses = buses
        self.connections = connections
        self.external_grids_config = external_grids_df
        self.external_grids = []
        
    def setup_external_grids(self):
        """Setup external grids based on config file or automatic selection"""
        if self.external_grids_config is not None and len(self.external_grids_config) > 0:
            self._use_config_file()
        else:
            self._auto_select_slack()
            
        print(f"External grids configured: {len(self.external_grids)}")
            
        return self.external_grids
        
    def _use_config_file(self):
        """Use external grids from configuration file"""
        # Check for duplicates
        bus_ids = self.external_grids_config['bus_id'].tolist()
        duplicates = [bid for bid in bus_ids if bus_ids.count(bid) > 1]
        
        if len(duplicates) > 0:
            unique_dups = list(set(duplicates))
            raise ValueError(f"Duplicate bus_ids in external_grids.csv: {unique_dups}")
        
        for _, row in self.external_grids_config.iterrows():
            bus_id = row['bus_id']
            
            if bus_id not in self.buses['bus_id'].values:
                print(f"  Warning: Bus {bus_id} not found, skipping")
                continue
                
            grid_type = row.get('grid_type', 'border')
            
            # Set va_degree: 0 for main slack, None for others
            va_degree = 0.0 if grid_type == 'main_slack' else None
                
            ext_grid = {
                'bus_id': bus_id,
                'vm_pu': row.get('vm_pu', config.DEFAULT_SLACK_VM_PU),
                'va_degree': va_degree,
                'max_p_mw': row.get('max_p_mw', 999999),
                'min_p_mw': row.get('min_p_mw', -999999),
                'country': row.get('country', 'Unknown'),
                'type': grid_type
            }
            self.external_grids.append(ext_grid)
            
    def _auto_select_slack(self):
        """Automatically select a slack bus"""
        # Filter 380kV buses (or 220kV as fallback)
        buses_380 = self.buses[self.buses['vn_kv'] == 380].copy()
        
        if len(buses_380) == 0:
            buses_380 = self.buses[self.buses['vn_kv'] == 220].copy()
            
        # Count connections for each bus
        from_counts = self.connections['from_bus_id'].value_counts()
        to_counts = self.connections['to_bus_id'].value_counts()
        total_counts = from_counts.add(to_counts, fill_value=0)
        
        buses_380['connection_count'] = buses_380['bus_id'].map(total_counts).fillna(0)
        buses_380 = buses_380.sort_values('connection_count', ascending=False)
        
        # Take top candidates and select closest to reference point
        candidates = buses_380.head(10).copy()
        ref_lat = config.SLACK_REFERENCE_LAT
        ref_lon = config.SLACK_REFERENCE_LON
        
        candidates['distance_to_ref'] = np.sqrt(
            (candidates['lat'] - ref_lat)**2 + (candidates['lon'] - ref_lon)**2
        )
        
        slack_bus = candidates.nsmallest(1, 'distance_to_ref').iloc[0]
        
        print(f"  Auto-selected slack: {slack_bus['name']} "
              f"({int(slack_bus['connection_count'])} connections)")
        
        ext_grid = {
            'bus_id': slack_bus['bus_id'],
            'vm_pu': config.DEFAULT_SLACK_VM_PU,
            'va_degree': config.DEFAULT_SLACK_VA_DEGREE,
            'max_p_mw': 999999,
            'min_p_mw': -999999,
            'country': 'Germany',
            'type': 'main_slack'
        }
        self.external_grids.append(ext_grid)