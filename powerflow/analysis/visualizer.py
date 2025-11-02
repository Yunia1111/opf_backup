"""
Professional Visualizer - High-quality power system visualization
Version 2: Enhanced generator visualization, HVDC support, scenario panel
"""
import folium
from folium import plugins
import json
import os
import config
import math

class Visualizer:
    def __init__(self, net=None):
        self.net = net
        self.map = None
        
        # Professional engineering color scheme
        self.voltage_colors = {
            380: '#9b59b6',  # Purple for EHV
            220: '#3498db',  # Blue for HV
            110: '#1abc9c'   # Teal for MV
        }
        
        self.voltage_status_colors = {
            'critical_low': '#8B0000',    # Dark red
            'low': '#DC143C',             # Crimson
            'normal': '#228B22',          # Forest green
            'high': '#FF8C00',            # Dark orange
            'critical_high': '#4B0082'    # Indigo
        }
        
        self.loading_colors = {
            'normal': '#2E8B57',      # Sea green
            'elevated': '#DAA520',    # Goldenrod
            'high': '#FF6347',        # Tomato
            'critical': '#8B008B'     # Dark magenta
        }
        
    def create_map(self):
        """Create professional engineering visualization"""
        print("Generating professional power system visualization...")
        
        data_path = os.path.join(config.OUTPUT_DIR, 'visualization_data.json')
        with open(data_path, 'r') as f:
            data = json.load(f)
        
        if len(data['buses']) == 0:
            print("  ⚠ No visualization data available")
            return
        
        # Calculate map center
        all_lats = [b['lat'] for b in data['buses']]
        all_lons = [b['lon'] for b in data['buses']]
        center_lat = sum(all_lats) / len(all_lats)
        center_lon = sum(all_lons) / len(all_lons)
        
        # Initialize map
        self.map = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=6,
            tiles='OpenStreetMap',
            prefer_canvas=True
        )
        
        # Add professional dark theme
        folium.TileLayer(
            tiles='https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
            attr='© CARTO',
            name='Dark Mode',
            control=True,
            opacity=0.8
        ).add_to(self.map)
        
        # Create layer structure
        voltage_levels = sorted(set(b['vn_kv'] for b in data['buses']))
        
        # Voltage-specific layers
        voltage_layers = {}
        for vn in voltage_levels:
            voltage_layers[vn] = {
                'lines': folium.FeatureGroup(name=f'{vn}kV Lines', show=(vn>=220)),
                'buses': folium.FeatureGroup(name=f'{vn}kV Substations', show=(vn>=220))
            }
        
        # Analysis layers
        power_flow_layer = folium.FeatureGroup(name='Power Flow (MW)', show=False)
        loading_layer = folium.FeatureGroup(name='Line Loading (%)', show=False)
        voltage_layer = folium.FeatureGroup(name='Voltage Profile', show=False)
        generation_layer = folium.FeatureGroup(name='Generation', show=True)
        load_layer = folium.FeatureGroup(name='Loads', show=False)
        
        # Build visualization
        line_voltage_map = self._build_line_voltage_map(data['lines'], data['buses'])
        
        self._add_lines(data['lines'], line_voltage_map, voltage_layers, 
                       power_flow_layer, loading_layer)
        self._add_buses(data['buses'], voltage_layers, voltage_layer)
        self._add_loads(data.get('loads', []), load_layer)
        self._add_generators(data['generators'], generation_layer)
        self._add_external_grids(data['external_grids'])
        
        # Add all layers to map
        for vn in voltage_levels:
            voltage_layers[vn]['lines'].add_to(self.map)
            voltage_layers[vn]['buses'].add_to(self.map)
        
        power_flow_layer.add_to(self.map)
        loading_layer.add_to(self.map)
        voltage_layer.add_to(self.map)
        generation_layer.add_to(self.map)
        load_layer.add_to(self.map)
        
        # Add controls
        folium.LayerControl(collapsed=False, position='topright').add_to(self.map)
        plugins.Fullscreen(position='topleft').add_to(self.map)
        plugins.MeasureControl(position='bottomleft', 
                              primary_length_unit='kilometers').add_to(self.map)
        
        # Add professional legend with generator types
        self._add_engineering_legend(voltage_levels)
        
        # Add scenario information panel
        self._add_scenario_panel()
        
        # Save
        output_path = os.path.join(config.OUTPUT_DIR, 'network_map.html')
        self.map.save(output_path)
        print(f"  ✓ Visualization saved: {output_path}")
    
    def _build_line_voltage_map(self, lines, buses):
        """Map line IDs to their voltage levels"""
        bus_voltage = {b['id']: b['vn_kv'] for b in buses}
        line_voltage = {}
        
        for line in lines:
            from_v = bus_voltage.get(line.get('from_bus_id'), 380)
            to_v = bus_voltage.get(line.get('to_bus_id'), 380)
            line_voltage[line['id']] = max(from_v, to_v)
        
        return line_voltage
    
    def _add_lines(self, lines, line_voltage_map, voltage_layers, 
                   power_flow_layer, loading_layer):
        """Add transmission lines with multi-layer support and real geographic paths"""
        
        for line in lines:
            line_vn = line_voltage_map.get(line['id'], 380)
            base_color = self.voltage_colors.get(line_vn, '#3498db')
            
            loading = line['loading_percent']
            power = abs(line['p_from_mw'])
            
            # Determine loading color
            if loading > 100:
                load_color = self.loading_colors['critical']
            elif loading > 80:
                load_color = self.loading_colors['high']
            elif loading > 60:
                load_color = self.loading_colors['elevated']
            else:
                load_color = self.loading_colors['normal']
            
            # Use real geographic coordinates if available
            if 'geo_coords' in line and line['geo_coords']:
                coords = line['geo_coords']
            else:
                # Fallback to straight line
                coords = [[line['from_lat'], line['from_lon']],
                         [line['to_lat'], line['to_lon']]]
            
            # Professional popup
            popup_html = self._create_line_popup(line, line_vn, base_color)
            tooltip = f"{line_vn}kV | {power:.0f} MW | {loading:.0f}%"
            
            # Base layer - simple line by voltage
            folium.PolyLine(
                locations=coords,
                popup=folium.Popup(popup_html, max_width=420),
                tooltip=tooltip,
                color=base_color,
                weight=2.5 if line_vn >= 380 else 2,
                opacity=0.75
            ).add_to(voltage_layers[line_vn]['lines'])
            
            # Power flow layer - width by power (SQRT scale - more visible)
            power_weight = 2.0 + math.sqrt(max(power, 1)) * 0.1
            folium.PolyLine(
                locations=coords,
                popup=folium.Popup(popup_html, max_width=420),
                tooltip=f"{power:.0f} MW",
                color='#FFA500',
                weight=power_weight,
                opacity=0.8
            ).add_to(power_flow_layer)
            
            # Loading layer - color by loading
            loading_weight = 2 + (loading / 40)
            folium.PolyLine(
                locations=coords,
                popup=folium.Popup(popup_html, max_width=420),
                tooltip=f"{loading:.1f}% loading",
                color=load_color,
                weight=loading_weight,
                opacity=0.85
            ).add_to(loading_layer)
    
    def _add_buses(self, buses, voltage_layers, voltage_layer):
        """Add substations with proper sizing"""
        
        for bus in buses:
            vn = bus['vn_kv']
            vm_pu = bus['vm_pu']
            
            base_color = self.voltage_colors.get(vn, '#3498db')
            status_color = self._get_voltage_status_color(vm_pu)
            
            # Size by voltage level (smaller than before)
            radius = 4 if vn >= 380 else 3
            
            popup_html = self._create_bus_popup(bus, base_color)
            tooltip = f"{bus['name'][:40]} | {vm_pu:.3f} pu"
            
            # Voltage level layer
            folium.CircleMarker(
                location=[bus['lat'], bus['lon']],
                radius=radius,
                popup=folium.Popup(popup_html, max_width=420),
                tooltip=tooltip,
                color='#2c3e50',
                weight=1,
                fillColor=base_color,
                fillOpacity=0.85
            ).add_to(voltage_layers[vn]['buses'])
            
            # Voltage profile layer
            folium.CircleMarker(
                location=[bus['lat'], bus['lon']],
                radius=radius + 1,
                popup=folium.Popup(popup_html, max_width=420),
                tooltip=f"{vm_pu:.4f} pu",
                color='white',
                weight=1,
                fillColor=status_color,
                fillOpacity=0.9
            ).add_to(voltage_layer)
    
    def _add_loads(self, loads, load_layer):
        """Add load markers with size by magnitude (INCREASED SIZE)"""
        
        if len(loads) == 0:
            return
        
        for load in loads:
            p_mw = load['p_mw']
            # Increased base size from 3 to 6, and increased scaling
            radius = max(6, 4 + math.log10(max(p_mw, 1)) * 2.5)
            
            popup_html = f"""
            <div style="font-family:Consolas,monospace; width:360px; padding:8px;">
                <table style="width:100%; border-collapse:collapse; font-size:13px;">
                    <tr style="background:#34495e; color:white;">
                        <th colspan="2" style="padding:8px; text-align:left;">
                            ⚡ LOAD - {load.get('name', 'N/A')[:35]}
                        </th>
                    </tr>
                    <tr><td style="padding:4px; font-weight:bold;">Active Power</td>
                        <td style="padding:4px; text-align:right;">{p_mw:.2f} MW</td></tr>
                    <tr><td style="padding:4px; font-weight:bold;">Reactive Power</td>
                        <td style="padding:4px; text-align:right;">{load.get('q_mvar', 0):.2f} Mvar</td></tr>
                </table>
            </div>
            """
            
            folium.CircleMarker(
                location=[load['lat'], load['lon']],
                radius=radius,
                popup=folium.Popup(popup_html, max_width=380),
                tooltip=f"Load: {p_mw:.1f} MW",
                color='#c0392b',
                weight=1,
                fillColor='#e74c3c',
                fillOpacity=0.7
            ).add_to(load_layer)
    
    def _add_generators(self, generators, generation_layer):
        """Add generators with TYPE-BASED COLORS and INCREASED SIZE"""
        
        if len(generators) == 0:
            return
        
        for gen in generators:
            sn_mva = gen['sn_mva']
            p_mw = gen['p_mw']
            gen_type = str(gen.get('type', 'other')).lower().strip()
            
            # Increased base size from 3 to 6, and increased scaling
            radius = max(6, 4 + math.log10(max(sn_mva, 1)) * 2.5)
            
            # Get color based on generator type
            color = self._get_generator_color(gen_type)
            
            popup_html = f"""
            <div style="font-family:Consolas,monospace; width:360px; padding:8px;">
                <table style="width:100%; border-collapse:collapse; font-size:13px;">
                    <tr style="background:{color}; color:white;">
                        <th colspan="2" style="padding:8px; text-align:left;">
                            ⚡ GENERATOR - {gen_type.upper()}
                        </th>
                    </tr>
                    <tr><td style="padding:4px; font-weight:bold;">Control Mode</td>
                        <td style="padding:4px; text-align:right;">{gen.get('control', 'PQ')}</td></tr>
                    <tr><td style="padding:4px; font-weight:bold;">Output</td>
                        <td style="padding:4px; text-align:right;">{p_mw:.2f} MW</td></tr>
                    <tr><td style="padding:4px; font-weight:bold;">Capacity</td>
                        <td style="padding:4px; text-align:right;">{sn_mva:.2f} MVA</td></tr>
                    <tr><td style="padding:4px; font-weight:bold;">Utilization</td>
                        <td style="padding:4px; text-align:right;">{p_mw/sn_mva*100:.1f}%</td></tr>
                </table>
            </div>
            """
            
            folium.CircleMarker(
                location=[gen['lat'], gen['lon']],
                radius=radius,
                popup=folium.Popup(popup_html, max_width=380),
                tooltip=f"{gen_type}: {p_mw:.0f} MW",
                color='#2c3e50',
                weight=1,
                fillColor=color,
                fillOpacity=0.8
            ).add_to(generation_layer)
    
    def _get_generator_color(self, gen_type):
        """Get color for generator based on type"""
        gen_type_lower = gen_type.lower().strip()
        
        # Try exact match first
        if gen_type_lower in config.GENERATOR_TYPE_COLORS:
            return config.GENERATOR_TYPE_COLORS[gen_type_lower]
        
        # Try partial match
        for key, color in config.GENERATOR_TYPE_COLORS.items():
            if key in gen_type_lower or gen_type_lower in key:
                return color
        
        # Default fallback
        return config.GENERATOR_TYPE_COLORS.get('other', '#95a5a6')
    
    def _add_external_grids(self, ext_grids):
        """Add external grid markers with HVDC identification"""
        
        ext_layer = folium.FeatureGroup(name='External Grids', show=True)
        
        for ext in ext_grids:
            # Check if this is an HVDC connection
            is_hvdc = 'HVDC' in ext['name'].upper() or 'HVDC' in str(ext.get('type', '')).upper()
            
            # Choose color and icon based on type
            if is_hvdc:
                icon_color = 'orange'
                icon_name = 'bolt'
                marker_color = config.HVDC_COLOR
            else:
                icon_color = 'red'
                icon_name = 'plug'
                marker_color = '#c0392b'
            
            popup_html = f"""
            <div style="font-family:Consolas,monospace; width:360px; padding:8px;">
                <table style="width:100%; border-collapse:collapse; font-size:13px;">
                    <tr style="background:{marker_color}; color:white;">
                        <th colspan="2" style="padding:8px; text-align:left;">
                            {'🔌 HVDC CONNECTION' if is_hvdc else '🔌 EXTERNAL GRID'}
                        </th>
                    </tr>
                    <tr><td style="padding:4px; font-weight:bold;">Connection</td>
                        <td style="padding:4px; text-align:right;">{ext['name'][:30]}</td></tr>
                    <tr><td style="padding:4px; font-weight:bold;">Power Exchange</td>
                        <td style="padding:4px; text-align:right;">{ext['p_mw']:.2f} MW</td></tr>
                    <tr><td style="padding:4px; font-weight:bold;">Reactive Power</td>
                        <td style="padding:4px; text-align:right;">{ext['q_mvar']:.2f} Mvar</td></tr>
                </table>
            </div>
            """
            
            folium.Marker(
                location=[ext['lat'], ext['lon']],
                popup=folium.Popup(popup_html, max_width=380),
                tooltip=f"{'HVDC' if is_hvdc else 'Grid'}: {ext['p_mw']:.0f} MW",
                icon=folium.Icon(color=icon_color, icon=icon_name, prefix='fa')
            ).add_to(ext_layer)
        
        ext_layer.add_to(self.map)
    
    def _create_bus_popup(self, bus, color):
        """Create professional bus popup"""
        vm_pu = bus['vm_pu']
        status = self._get_voltage_status_text(vm_pu)
        status_color = self._get_voltage_status_color(vm_pu)
        
        return f"""
        <div style="font-family:Consolas,monospace; width:400px; padding:8px;">
            <table style="width:100%; border-collapse:collapse; font-size:13px;">
                <tr style="background:{color}; color:white;">
                    <th colspan="2" style="padding:10px; text-align:left; font-size:14px;">
                        {bus['name'][:45]}
                    </th>
                </tr>
                <tr style="background:#ecf0f1;">
                    <td colspan="2" style="padding:6px; font-weight:bold; font-size:12px;">
                        ELECTRICAL PARAMETERS
                    </td>
                </tr>
                <tr><td style="padding:4px; font-weight:bold; width:50%;">Nominal Voltage</td>
                    <td style="padding:4px; text-align:right;">{bus['vn_kv']:.0f} kV</td></tr>
                <tr><td style="padding:4px; font-weight:bold;">Voltage (pu)</td>
                    <td style="padding:4px; text-align:right;">{vm_pu:.4f}</td></tr>
                <tr><td style="padding:4px; font-weight:bold;">Voltage (kV)</td>
                    <td style="padding:4px; text-align:right;">{vm_pu * bus['vn_kv']:.2f}</td></tr>
                <tr><td style="padding:4px; font-weight:bold;">Phase Angle</td>
                    <td style="padding:4px; text-align:right;">{bus['va_degree']:.3f}°</td></tr>
                <tr><td style="padding:4px; font-weight:bold;">Status</td>
                    <td style="padding:4px; text-align:right; color:{status_color}; font-weight:bold;">
                        {status}
                    </td></tr>
                <tr style="background:#ecf0f1;">
                    <td colspan="2" style="padding:6px; font-weight:bold; font-size:12px;">
                        GEOGRAPHIC DATA
                    </td>
                </tr>
                <tr><td style="padding:4px; font-weight:bold;">Latitude</td>
                    <td style="padding:4px; text-align:right;">{bus['lat']:.6f}°</td></tr>
                <tr><td style="padding:4px; font-weight:bold;">Longitude</td>
                    <td style="padding:4px; text-align:right;">{bus['lon']:.6f}°</td></tr>
            </table>
        </div>
        """
    
    def _create_line_popup(self, line, vn, color):
        """Create professional line popup"""
        loading = line['loading_percent']
        status_color = self._get_loading_color(loading)
        
        return f"""
        <div style="font-family:Consolas,monospace; width:400px; padding:8px;">
            <table style="width:100%; border-collapse:collapse; font-size:13px;">
                <tr style="background:{color}; color:white;">
                    <th colspan="2" style="padding:10px; text-align:left; font-size:14px;">
                        {vn}kV TRANSMISSION LINE
                    </th>
                </tr>
                <tr style="background:#ecf0f1;">
                    <td colspan="2" style="padding:6px; font-weight:bold;">POWER FLOW</td>
                </tr>
                <tr><td style="padding:4px; font-weight:bold;">Active Power</td>
                    <td style="padding:4px; text-align:right;">{line['p_from_mw']:.2f} MW</td></tr>
                <tr><td style="padding:4px; font-weight:bold;">Reactive Power</td>
                    <td style="padding:4px; text-align:right;">{line.get('q_from_mvar',0):.2f} Mvar</td></tr>
                <tr><td style="padding:4px; font-weight:bold;">Current</td>
                    <td style="padding:4px; text-align:right;">{line.get('i_from_ka',0):.3f} kA</td></tr>
                <tr style="background:#ecf0f1;">
                    <td colspan="2" style="padding:6px; font-weight:bold;">LOADING ANALYSIS</td>
                </tr>
                <tr><td style="padding:4px; font-weight:bold;">Loading</td>
                    <td style="padding:4px; text-align:right; color:{status_color}; font-weight:bold;">
                        {loading:.2f}%
                    </td></tr>
                <tr><td style="padding:4px; font-weight:bold;">Current / Rating</td>
                    <td style="padding:4px; text-align:right;">
                        {line.get('i_from_ka',0):.3f} / {line.get('max_i_ka',0):.3f} kA
                    </td></tr>
                <tr style="background:#ecf0f1;">
                    <td colspan="2" style="padding:6px; font-weight:bold;">LINE CONFIGURATION</td>
                </tr>
                <tr><td style="padding:4px; font-weight:bold;">Parallel Circuits</td>
                    <td style="padding:4px; text-align:right;">{line['parallel']}</td></tr>
                <tr><td style="padding:4px; font-weight:bold;">Cables/Phase</td>
                    <td style="padding:4px; text-align:right;">{line.get('cables_per_phase',1)}</td></tr>
                <tr><td style="padding:4px; font-weight:bold;">Length</td>
                    <td style="padding:4px; text-align:right;">{line.get('length_km',0):.2f} km</td></tr>
                <tr style="background:#ecf0f1;">
                    <td colspan="2" style="padding:6px; font-weight:bold;">ELECTRICAL PARAMETERS</td>
                </tr>
                <tr><td style="padding:4px; font-weight:bold;">Resistance</td>
                    <td style="padding:4px; text-align:right;">{line.get('r_ohm_per_km',0):.5f} Ω/km</td></tr>
                <tr><td style="padding:4px; font-weight:bold;">Reactance</td>
                    <td style="padding:4px; text-align:right;">{line.get('x_ohm_per_km',0):.5f} Ω/km</td></tr>
                <tr><td style="padding:4px; font-weight:bold;">Capacitance</td>
                    <td style="padding:4px; text-align:right;">{line.get('c_nf_per_km',0):.2f} nF/km</td></tr>
            </table>
        </div>
        """
    
    def _add_engineering_legend(self, voltage_levels):
        """Add professional engineering legend with generator types"""
        legend_html = """
        <div style="position:fixed; bottom:60px; left:20px; width:260px; 
                    background:rgba(255,255,255,0.95); border:2px solid #2c3e50; 
                    z-index:9999; font-size:11px; padding:10px; border-radius:4px;
                    font-family:Consolas,monospace; box-shadow:0 2px 8px rgba(0,0,0,0.3);
                    max-height:500px; overflow-y:auto;">
        <div style="font-weight:bold; font-size:12px; margin-bottom:8px; 
                    border-bottom:2px solid #2c3e50; padding-bottom:4px;">
            VOLTAGE LEVELS
        </div>
        """
        
        for vn in voltage_levels:
            color = self.voltage_colors.get(vn, '#3498db')
            legend_html += f'''
            <div style="margin:3px 0; display:flex; align-items:center;">
                <div style="background:{color}; width:14px; height:14px; 
                     border-radius:2px; margin-right:6px; border:1px solid #2c3e50;"></div>
                <span>{vn} kV</span>
            </div>
            '''
        
        # Add generator type legend
        legend_html += """
        <div style="font-weight:bold; font-size:12px; margin:10px 0 6px 0; 
                    border-bottom:2px solid #2c3e50; padding-bottom:4px;">
            GENERATOR TYPES
        </div>
        """
        
        # Show main generator types with their colors
        gen_types_to_show = [
            ('wind_offshore', 'Wind Offshore'),
            ('wind_onshore', 'Wind Onshore'),
            ('solar_radiant_energy', 'Solar'),
            ('water', 'Hydro'),
            ('biomass', 'Biomass'),
            ('natural_gas', 'Natural Gas'),
            ('storage', 'Storage'),
            ('other', 'Other')
        ]
        
        for type_key, type_label in gen_types_to_show:
            color = config.GENERATOR_TYPE_COLORS.get(type_key, '#95a5a6')
            legend_html += f'''
            <div style="margin:3px 0; display:flex; align-items:center;">
                <div style="background:{color}; width:12px; height:12px; 
                     border-radius:50%; margin-right:6px; border:1px solid #2c3e50;"></div>
                <span style="font-size:10px;">{type_label}</span>
            </div>
            '''
        
        # Add HVDC legend
        legend_html += f"""
        <div style="font-weight:bold; font-size:12px; margin:10px 0 6px 0; 
                    border-bottom:2px solid #2c3e50; padding-bottom:4px;">
            SPECIAL CONNECTIONS
        </div>
        <div style="margin:3px 0; display:flex; align-items:center;">
            <div style="background:{config.HVDC_COLOR}; width:14px; height:14px; 
                 border-radius:2px; margin-right:6px; border:1px solid #2c3e50;"></div>
            <span>HVDC Converter</span>
        </div>
        """
        
        legend_html += """
        <div style="font-weight:bold; font-size:12px; margin:10px 0 6px 0; 
                    border-bottom:2px solid #2c3e50; padding-bottom:4px;">
            VOLTAGE STATUS
        </div>
        <div style="margin:3px 0;"><span style="color:#228B22;">●</span> Normal (0.95-1.05)</div>
        <div style="margin:3px 0;"><span style="color:#FF8C00;">●</span> Warning</div>
        <div style="margin:3px 0;"><span style="color:#DC143C;">●</span> Critical</div>
        
        <div style="font-weight:bold; font-size:12px; margin:10px 0 6px 0; 
                    border-bottom:2px solid #2c3e50; padding-bottom:4px;">
            LINE LOADING
        </div>
        <div style="margin:3px 0;"><span style="color:#2E8B57;">●</span> Normal (&lt;60%)</div>
        <div style="margin:3px 0;"><span style="color:#DAA520;">●</span> Elevated (60-80%)</div>
        <div style="margin:3px 0;"><span style="color:#FF6347;">●</span> High (80-100%)</div>
        <div style="margin:3px 0;"><span style="color:#8B008B;">●</span> Overload (&gt;100%)</div>
        </div>
        """
        
        self.map.get_root().html.add_child(folium.Element(legend_html))
    
    def _add_scenario_panel(self):
        """Add expandable scenario information panel"""
        # Get capacity factors and scaling factors from config
        cf_html = ""
        for gen_type, cf in config.GENERATION_CAPACITY_FACTORS.items():
            if not gen_type in ['wind', 'solar', 'hydro', 'gas', 'other']:  # Skip fallback patterns
                cf_html += f'<div style="margin:2px 0; font-size:10px;">{gen_type}: {cf}</div>'
        
        scenario_html = f"""
        <div style="position:fixed; bottom:40px; right:20px; z-index:9999;">
            <button id="scenario-toggle" style="
                padding:8px 12px; background:#3498db; color:white; border:none;
                border-radius:4px; cursor:pointer; font-size:12px; font-weight:bold;
                box-shadow:0 2px 4px rgba(0,0,0,0.3);">
                📊 Scenario Info
            </button>
            <div id="scenario-panel" style="
                display:none; margin-top:5px; width:300px; 
                background:rgba(255,255,255,0.95); border:2px solid #3498db; 
                border-radius:4px; padding:10px; font-family:Consolas,monospace;
                box-shadow:0 2px 8px rgba(0,0,0,0.3); max-height:400px; overflow-y:auto;">
                <div style="font-weight:bold; font-size:13px; margin-bottom:8px; 
                            border-bottom:2px solid #3498db; padding-bottom:4px; color:#2c3e50;">
                    SCENARIO PARAMETERS
                </div>
                <div style="margin:8px 0;">
                    <div style="font-weight:bold; font-size:11px; color:#2c3e50; margin-bottom:4px;">
                        Scaling Factors:
                    </div>
                    <div style="font-size:10px; padding-left:8px;">
                        Generation: {config.GENERATION_SCALING_FACTOR}
                    </div>
                    <div style="font-size:10px; padding-left:8px;">
                        Load: {config.LOAD_SCALING_FACTOR}
                    </div>
                </div>
                <div style="margin:8px 0;">
                    <div style="font-weight:bold; font-size:11px; color:#2c3e50; margin-bottom:4px;">
                        Capacity Factors:
                    </div>
                    <div style="padding-left:8px;">
                        {cf_html}
                    </div>
                </div>
            </div>
        </div>
        <script>
        document.getElementById('scenario-toggle').onclick = function() {{
            var panel = document.getElementById('scenario-panel');
            if (panel.style.display === 'none') {{
                panel.style.display = 'block';
            }} else {{
                panel.style.display = 'none';
            }}
        }};
        </script>
        """
        
        self.map.get_root().html.add_child(folium.Element(scenario_html))
    
    def _get_voltage_status_color(self, vm_pu):
        """Get voltage status color"""
        if vm_pu < 0.90:
            return self.voltage_status_colors['critical_low']
        elif vm_pu < 0.95:
            return self.voltage_status_colors['low']
        elif vm_pu <= 1.05:
            return self.voltage_status_colors['normal']
        elif vm_pu <= 1.10:
            return self.voltage_status_colors['high']
        else:
            return self.voltage_status_colors['critical_high']
    
    def _get_voltage_status_text(self, vm_pu):
        """Get voltage status text"""
        if vm_pu < 0.90:
            return 'CRITICAL LOW'
        elif vm_pu < 0.95:
            return 'LOW'
        elif vm_pu <= 1.05:
            return 'NORMAL'
        elif vm_pu <= 1.10:
            return 'HIGH'
        else:
            return 'CRITICAL HIGH'
    
    def _get_loading_color(self, loading):
        """Get loading status color"""
        if loading > 100:
            return self.loading_colors['critical']
        elif loading > 80:
            return self.loading_colors['high']
        elif loading > 60:
            return self.loading_colors['elevated']
        else:
            return self.loading_colors['normal']