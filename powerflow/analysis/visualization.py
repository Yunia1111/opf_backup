"""
Visualizer - Generates interactive folium maps of the power grid.
Minimizable Dashboard, Split Layers, Pie Charts, HVDC Lines.
"""
import folium
from folium import plugins
from folium.features import DivIcon
import json
import os
from . import config
import math
from collections import defaultdict
from .scenarios import SCENARIOS 

class Visualizer:
    def __init__(self):
        self.output_dir = config.OUTPUT_DIR
        self.voltage_colors = {380: '#8E44AD', 220: '#2980B9', 110: '#16A085'}
        self.loading_colors = {'normal': '#27ae60', 'elevated': '#f39c12', 'high': '#e67e22', 'critical': '#c0392b'}

    def create_map(self, scenario_net, scenario_info):
        scenario_name_folder = scenario_info['name'].replace(' ', '_').lower()
        data_path = os.path.join(config.OUTPUT_DIR, scenario_name_folder, 'visualization_data.json')
        try:
            with open(data_path, 'r') as f: data = json.load(f)
        except: return

        if not data['buses']: return
        
        lats = [b['lat'] for b in data['buses']]
        lons = [b['lon'] for b in data['buses']]
        m = folium.Map(location=[sum(lats)/len(lats), sum(lons)/len(lons)], zoom_start=6, tiles=None, prefer_canvas=True)
        folium.TileLayer('CartoDB dark_matter', name='🌑 Dark Mode').add_to(m)
        folium.TileLayer('CartoDB positron', name='☀️ Light Mode').add_to(m)
        
        # Layers
        layer_grid_380 = folium.FeatureGroup(name='380kV Grid', show=False)
        layer_grid_220 = folium.FeatureGroup(name='220kV Grid', show=False)
        layer_hvdc = folium.FeatureGroup(name='HVDC Corridors', show=True) 
        layer_loading = folium.FeatureGroup(name='Line Loading', show=True)
        layer_gen = folium.FeatureGroup(name='Generation', show=True)
        layer_border = folium.FeatureGroup(name='Border Flows', show=True)
        layer_inj = folium.FeatureGroup(name='Injection Analysis', show=True)
        layer_disc = folium.FeatureGroup(name='Disconnected Components', show=True) 
        layer_trafos   = folium.FeatureGroup(name='Transformers', show=True)
        layer_loads    = folium.FeatureGroup(name='Loads', show=True)

        # Lines (AC)
        line_v_map = self._map_line_voltages(data['lines'], data['buses'])
        for line in data['lines']:
            vn = line_v_map.get(line['id'], 380)
            target = layer_grid_380 if vn >= 380 else layer_grid_220
            self._add_detailed_line(line, vn, target, False)
            self._add_detailed_line(line, vn, layer_loading, True)
        
        # HVDC Lines
        if 'dclines' in data:
            for dc in data['dclines']:
                coords = [[dc['from_lat'], dc['from_lon']], [dc['to_lat'], dc['to_lon']]]
                util = abs(dc['p_mw']) / dc['capacity'] * 100 if dc['capacity'] > 0 else 0
                popup = f"<b>HVDC: {dc['name']}</b><br>Flow: {dc['p_mw']:.1f} MW<br>Util: {util:.1f}%"
                folium.PolyLine(coords, color='#FF6B35', weight=4, dash_array='10, 10', opacity=1, popup=popup, tooltip=f"HVDC {dc['p_mw']:.0f} MW").add_to(layer_hvdc)

        # Buses
        for bus in data['buses']:
            target = layer_grid_380 if bus['vn_kv'] >= 380 else layer_grid_220
            self._add_detailed_bus(bus, target)
        
        # Disconnected Buses
        if 'disconnected' in data and len(data['disconnected']) > 0:
            for db in data['disconnected']:
                popup = f"Disconnected Bus: {db['name']} ({db['vn_kv']}kV)"
                folium.CircleMarker(
                    [db['lat'], db['lon']], 
                    radius=3, color='#7f8c8d', fill=True, fill_color='#7f8c8d', fill_opacity=0.6,
                    popup=popup
                ).add_to(layer_disc)

        # Generators
        self._add_aggregated_generators(data['generators'], layer_gen, layer_border, layer_inj)
        for eg in data['external_grids']:
            folium.Marker([eg['lat'], eg['lon']], popup=f"Slack: {eg['p_mw']:.1f}MW", icon=folium.Icon(color='red', icon='plug', prefix='fa')).add_to(layer_border)

        # trafos
        if 'trafos' in data:
            for t in data['trafos']:
                coords = [[t['hv_lat'], t['hv_lon']], [t['lv_lat'], t['lv_lon']]]
                popup_html = f"<b>TRAFO: {t['name']}</b><br>Load: {t['loading_percent']:.1f}%"
                
                folium.PolyLine(coords, color='orange', weight=3, dash_array='5, 5', opacity=0.8).add_to(layer_trafos)
                
                folium.CircleMarker(
                    [t['hv_lat'], t['hv_lon']], 
                    radius=4, 
                    color='orange', fill=True, fill_opacity=1.0,
                    popup=popup_html
                ).add_to(layer_trafos)

        # Loads
        if 'loads' in data:
            for l in data['loads']:
                # size = min(50, max(14, 10 + math.log(total_p)*4))
                # generators: (DivIcon size), load: CircleMarker (radius), so radius = size / 2
                p_val = abs(l['p_mw'])
                if p_val < 1: 
                    p_val = 1.0 
                diameter = min(50, max(14, 10 + math.log(p_val) * 4))
                diameter = diameter * 0.85
                radius = diameter / 2.0

                popup_html = f"""
                <b>LOAD: {l['name']}</b><br>
                P: {l['p_mw']:.1f} MW<br>
                Q: {l['q_mvar']:.1f} MVar
                """
                
                folium.CircleMarker(
                    [l['lat'], l['lon']], 
                    radius=radius,
                    color='#e74c3c', 
                    fill=True, 
                    fill_opacity=0.6,    
                    popup=popup_html,
                    tooltip=f"Load: {l['p_mw']:.0f} MW"
                ).add_to(layer_loads)


        for l in [layer_grid_380, layer_grid_220, layer_loading, layer_gen, layer_loads, layer_trafos, layer_hvdc, layer_border, layer_disc, layer_inj]: l.add_to(m)
        
        self._add_scenario_dashboard(m, scenario_info)
        self._add_unified_legend(m)
        
        folium.LayerControl(collapsed=True, position='topleft').add_to(m)
        plugins.Fullscreen(position='topleft').add_to(m)
        
        m.save(os.path.join(config.OUTPUT_DIR, scenario_name_folder, f'{scenario_name_folder}_map.html'))
        print(f"  ✓ Visualization saved.")

    def _add_aggregated_generators(self, gens, gen_layer, border_layer, inj_layer):
        loc_groups = defaultdict(list)
        for gen in gens: loc_groups[(round(gen['lat'],4), round(gen['lon'],4))].append(gen)
        
        for (lat, lon), group in loc_groups.items():
            special = [g for g in group if g['type'] in ['border', 'virtual_injection']]
            normal = [g for g in group if g['type'] not in ['border', 'virtual_injection']]
            
            for g in special:
                if g['type'] == 'virtual_injection':
                    html = f"<b>📍 INJECTION</b><br>Cap: {g['p_mw']:.1f} MW"
                    folium.Marker([lat, lon], popup=html, icon=folium.Icon(color='green', icon='bolt', prefix='fa')).add_to(inj_layer)
                    folium.Circle([lat, lon], radius=5000, color='#2ecc71', fill=True).add_to(inj_layer)
                else:
                    direct = "IMPORT" if g['p_mw'] > 0 else "EXPORT"
                    html = f"<b>{g['name']}</b><br>Flow: {g['p_mw']:.1f} MW ({direct})"
                    folium.Marker([lat, lon], popup=html, icon=folium.Icon(color='darkblue', icon='exchange', prefix='fa')).add_to(border_layer)
            
            if normal: self._create_pie_marker(lat, lon, normal, gen_layer)

    def _create_pie_marker(self, lat, lon, gen_list, layer):
        total_p = sum(abs(g['p_mw']) for g in gen_list)
        if total_p < 1: return
        gen_list.sort(key=lambda x: abs(x['p_mw']), reverse=True)
        
        segments, curr_deg, rows = [], 0, ""
        for g in gen_list:
            p_abs = abs(g['p_mw'])
            if p_abs < 0.1: continue
            deg = (p_abs / total_p) * 360
            color = config.GENERATOR_TYPE_COLORS.get(g['type'].lower(), '#999')
            segments.append(f"{color} {curr_deg:.1f}deg {curr_deg+deg:.1f}deg")
            curr_deg += deg
            rows += f"<tr><td>{g['type']}</td><td style='text-align:right'>{g['p_mw']:.1f}</td></tr>"
            
        size = min(50, max(14, 10 + math.log(total_p)*4))
        size = size * 0.85
        icon = f'<div style="width:{size}px;height:{size}px;border-radius:50%;background:conic-gradient({", ".join(segments)});border:2px solid white;box-shadow:2px 2px 5px rgba(0,0,0,0.5);"></div>'
        popup = f"<div style='font-family:sans-serif;font-size:12px;'><b>Hub Gen: {total_p:.1f} MW</b><table>{rows}</table></div>"
        folium.Marker([lat, lon], icon=DivIcon(html=icon, icon_size=(size, size), icon_anchor=(size/2, size/2)), popup=folium.Popup(popup, max_width=300)).add_to(layer)

    def _add_detailed_line(self, line, vn, layer, is_loading):
        coords = line.get('geo_coords', [[line['from_lat'], line['from_lon']], [line['to_lat'], line['to_lon']]])
        if is_loading:
            load = line['loading_percent']
            color = self.loading_colors['normal']
            if load > 100: color = self.loading_colors['critical']
            elif load > 80: color = self.loading_colors['high']
            elif load > 60: color = self.loading_colors['elevated']
            weight = 4 + (load/40)
        else:
            color = self.voltage_colors.get(vn, '#999')
            weight = 4 if vn >= 380 else 3
            
        popup = self._create_line_popup_html(line, vn)
        folium.PolyLine(coords, color=color, weight=weight, opacity=0.8, popup=folium.Popup(popup, max_width=350)).add_to(layer)

    def _add_detailed_bus(self, bus, layer):
        color = self.voltage_colors.get(bus['vn_kv'], '#999')
        popup = self._create_bus_popup_html(bus)
        folium.CircleMarker([bus['lat'], bus['lon']], radius=4, color='#333', weight=1, fill_color=color, fill_opacity=0.9, popup=folium.Popup(popup, max_width=300)).add_to(layer)

    def _create_line_popup_html(self, line, vn):
        status = "red" if line['loading_percent'] > 100 else "green"
        return f"""<div style='font-family:sans-serif;font-size:12px;width:100%;'>
        <div style='background:#34495e;color:white;padding:5px;'><b>LINE: {line['name']}</b> ({vn:.0f}kV)</div>
        <table style='width:100%;margin-top:5px;'>
        <tr><td>From/To</td><td style='text-align:right'>{line['from_bus_id']} → {line['to_bus_id']}</td></tr>
        <tr><td>Loading</td><td style='text-align:right;color:{status};'><b>{line['loading_percent']:.1f}%</b></td></tr>
        <tr><td colspan=2 style='border-bottom:1px solid #ccc'></td></tr>
        <tr><td>P (From)</td><td style='text-align:right'>{line.get('p_from_mw',0):.1f} MW</td></tr>
        <tr><td>Q (From)</td><td style='text-align:right'>{line.get('q_from_mvar',0):.1f} MVar</td></tr>
        <tr><td>Losses</td><td style='text-align:right'>{(abs(line.get('p_from_mw',0)) - abs(line.get('p_to_mw',0))):.2f} MW</td></tr>
        </table></div>"""

    def _create_bus_popup_html(self, bus):
        return f"""<div style='font-family:sans-serif;font-size:12px;'>
        <div style='background:#2980b9;color:white;padding:5px;'><b>BUS: {bus['name']}</b></div>
        <table style='width:100%;margin-top:5px;'>
        <tr><td>Voltage Level</td><td style='text-align:right'>{bus['vn_kv']:.0f} kV</td></tr>
        <tr><td>Actual Voltage</td><td style='text-align:right'>{(bus['vm_pu']*bus['vn_kv']):.2f} kV</td></tr>
        <tr><td>Per Unit</td><td style='text-align:right'>{bus['vm_pu']:.3f} pu</td></tr>
        <tr><td>Angle</td><td style='text-align:right'>{bus.get('va_degree', 0):.2f}°</td></tr>
        </table></div>"""

    def _map_line_voltages(self, lines, buses):
        b_v = {b['id']: b['vn_kv'] for b in buses}
        return {l['id']: max(b_v.get(l['from_bus_id'], 380), b_v.get(l['to_bus_id'], 380)) for l in lines}

    def _add_scenario_dashboard(self, m, info):
        cfs = info.get('gen_by_type', {})
        total = info.get('total_gen_mw', 1)
        active_cfs = {}
        for k, v in SCENARIOS.items():
            if info['name'] == v['name']:
                active_cfs = v['capacity_factors']
                break
        
        mix = ""
        for k, v in sorted(cfs.items(), key=lambda x:x[1], reverse=True)[:8]:
            pct = (v/total)*100
            color = config.GENERATOR_TYPE_COLORS.get(k, '#333')
            cf_disp = "N/A"
            for ck, cv in active_cfs.items():
                if ck in k: cf_disp = f"{cv:.2f}"; break
            mix += f"""<div style="display:flex;justify-content:space-between;margin-bottom:2px;border-bottom:1px solid #eee;">
            <span><span style="color:{color}">●</span> {k}</span>
            <span style="font-size:10px;color:#666;margin-right:5px;">CF:{cf_disp}</span>
            <b>{v:.0f} MW</b></div>"""

        html = f"""<div id="dashboard" style="position:fixed;top:10px;right:10px;width:260px;background:rgba(255,255,255,0.95);border-left:5px solid #2980b9;padding:10px;z-index:900;font-family:sans-serif;font-size:11px;box-shadow:0 4px 10px rgba(0,0,0,0.2);">
        <div onclick="document.getElementById('dash-content').style.display = document.getElementById('dash-content').style.display==='none'?'block':'none'" style="cursor:pointer;display:flex;justify-content:space-between;">
        <h3 style="margin:0;">📊 {info['name']}</h3><span>▼</span></div>
        <div id="dash-content">
        <div style="margin:5px 0;display:grid;grid-template-columns:1fr 1fr;gap:5px;">
        <div style="background:#eafaf1;padding:5px;text-align:center;"><b style="color:#27ae60">GEN {info.get('total_gen_mw',0)/1000:.1f} GW</b></div>
        <div style="background:#fdedec;padding:5px;text-align:center;"><b style="color:#c0392b">LOAD {info.get('total_load_mw',0)/1000:.1f} GW</b></div>
        </div><div style="max-height:300px;overflow-y:auto;">{mix}</div></div></div>"""
        m.get_root().html.add_child(folium.Element(html))

    def _add_unified_legend(self, m):
        gen_html = "".join([f'<div style="margin-bottom:2px;"><span style="background:{c};width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px;"></span>{k}</div>' for k,c in sorted(config.GENERATOR_TYPE_COLORS.items()) if k!='default'])
        html = f"""<div style="position:fixed;bottom:20px;right:10px;width:180px;max-height:200px;overflow-y:auto;background:rgba(255,255,255,0.9);border:1px solid #ccc;border-radius:5px;padding:8px;z-index:999;font-family:sans-serif;font-size:10px;">
        <h4 style="margin:0 0 5px 0;">Legend</h4>
        <b>Voltage</b><br><span style="color:#8E44AD">■ 380kV</span> <span style="color:#2980B9">■ 220kV</span> <span style="color:#FF6B35">-- HVDC</span><br>
        <span style="color:#7f8c8d;font-size:12px;">⚪ Disconnected</span><br>
        <div style="margin-top:5px;"><b>Line Loading</b><br>
        <span style="color:#27ae60">■ &lt;60%</span> <span style="color:#f39c12">■ 60-80%</span><br>
        <span style="color:#e67e22">■ 80-100%</span> <span style="color:#c0392b">■ &gt;100%</span></div>
        <div style="margin-top:5px;"><b>Generators</b><br>{gen_html}</div>
        </div>"""
        m.get_root().html.add_child(folium.Element(html))