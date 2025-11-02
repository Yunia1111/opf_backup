"""
Network cleaner - removes isolated components
"""
import pandapower.topology as top

class NetworkCleaner:
    def __init__(self, net):
        self.net = net
        
    def clean_isolated_networks(self):
        """Remove isolated components, keep only main network"""
        mg = top.create_nxgraph(self.net, respect_switches=False)
        import networkx as nx
        components = list(nx.connected_components(mg))
        
        if len(components) == 1:
            print("  ✓ Network is fully connected")
            return self.net
            
        # Keep only main component
        main_component = max(components, key=len)
        buses_to_keep = set(main_component)
        
        print(f"  Removing {len(components)-1} isolated components "
              f"(keeping {len(main_component)} buses)")
        
        self._filter_elements(buses_to_keep)
        return self.net
        
    def fix_transformers(self):
        """Remove transformers connecting same voltage levels"""
        if len(self.net.trafo) == 0:
            return self.net
            
        same_voltage_trafos = []
        for idx, trafo in self.net.trafo.iterrows():
            hv_vn = self.net.bus.at[trafo['hv_bus'], 'vn_kv']
            lv_vn = self.net.bus.at[trafo['lv_bus'], 'vn_kv']
            if hv_vn == lv_vn:
                same_voltage_trafos.append(idx)
                
        if len(same_voltage_trafos) > 0:
            self.net.trafo = self.net.trafo.drop(same_voltage_trafos)
            print(f"  Removed {len(same_voltage_trafos)} invalid transformers")
        else:
            print("  ✓ All transformers OK")
            
        return self.net
        
    def _filter_elements(self, buses_to_keep):
        """Filter all network elements to keep only specified buses"""
        self.net.bus = self.net.bus[self.net.bus.index.isin(buses_to_keep)]
        self.net.line = self.net.line[
            (self.net.line['from_bus'].isin(buses_to_keep)) & 
            (self.net.line['to_bus'].isin(buses_to_keep))
        ]
        self.net.trafo = self.net.trafo[
            (self.net.trafo['hv_bus'].isin(buses_to_keep)) & 
            (self.net.trafo['lv_bus'].isin(buses_to_keep))
        ]
        self.net.gen = self.net.gen[self.net.gen['bus'].isin(buses_to_keep)]
        self.net.sgen = self.net.sgen[self.net.sgen['bus'].isin(buses_to_keep)]
        self.net.load = self.net.load[self.net.load['bus'].isin(buses_to_keep)]
        self.net.ext_grid = self.net.ext_grid[self.net.ext_grid['bus'].isin(buses_to_keep)]