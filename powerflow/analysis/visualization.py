"""
Visualizer - Generates interactive folium maps of the power grid.
FIXED: Correctly calculates total capacity for parallel lines.
FIXED: Storage markers are now smaller
"""
import folium
from folium import plugins
from folium.features import DivIcon
import json
import os
import ast
from . import config
import math
from collections import defaultdict
from .scenarios import SCENARIOS 

class Visualizer:
    def __init__(self):
        self.output_dir = config.OUTPUT_DIR
        self.voltage_colors = {380: '#8E44AD', 220: '#2980B9', 110: '#16A085'}
        self.loading_colors = {'normal': '#27ae60', 'elevated': '#f39c12', 'high': '#e67e22', 'critical': '#c0392b'}

    def get_voltage_status_color(self, vm_pu):
        if vm_pu > 1.05: return '#e74c3c'
        if vm_pu < 0.95: return '#3498db'
        return '#2ecc71'

    def create_map(self, scenario_net, scenario_info, result_folder=None):
        if result_folder:
            scenario_name_folder = result_folder
        else:
            scenario_name_folder = scenario_info['name'].replace(' ', '_').lower()
            
        data_path = os.path.join(config.OUTPUT_DIR, scenario_name_folder, 'visualization_data.json')
        
        try:
            with open(data_path, 'r') as f: data = json.load(f)
        except FileNotFoundError: return

        if not data['buses']: return
        
        lats = [b['lat'] for b in data['buses']]
        lons = [b['lon'] for b in data['buses']]
        m = folium.Map(location=[sum(lats)/len(lats), sum(lons)/len(lons)], zoom_start=6, tiles=None, prefer_canvas=True)
        folium.TileLayer('CartoDB dark_matter', name='🌑 Dark Mode').add_to(m)
        folium.TileLayer('CartoDB positron', name='☀️ Light Mode').add_to(m)
        
        layer_grid_380 = folium.FeatureGroup(name='380kV Grid (Voltage Status)', show=False)
        layer_grid_220 = folium.FeatureGroup(name='220kV Grid (Voltage Status)', show=False)
        layer_dc_lines = folium.FeatureGroup(name='DC Lines', show=True)  
        layer_loading  = folium.FeatureGroup(name='Line Loading', show=True)
        layer_gen      = folium.FeatureGroup(name='Generation (Pie Charts)', show=False)
        layer_storage  = folium.FeatureGroup(name='Storage Units', show=False)
        layer_border   = folium.FeatureGroup(name='Border Flows (Arrows)', show=True)
        layer_inj      = folium.FeatureGroup(name='Injection Analysis', show=True)
        layer_disc     = folium.FeatureGroup(name='Disconnected Components', show=False) 
        layer_trafos   = folium.FeatureGroup(name='Transformers', show=False)
        layer_loads    = folium.FeatureGroup(name='Loads', show=False)

        line_v_map = self._map_line_voltages(data['lines'], data['buses'])
        for line in data['lines']:
            vn = line_v_map.get(line['id'], 380)
            target = layer_grid_380 if vn >= 380 else layer_grid_220
            self._add_detailed_line(line, vn, target, False)
            self._add_detailed_line(line, vn, layer_loading, True)
        
        if 'dclines' in data:
            for dc in data['dclines']:
                coords = [[dc['from_lat'], dc['from_lon']], [dc['to_lat'], dc['to_lon']]]
                util = abs(dc['p_mw']) / dc['capacity'] * 100 if dc['capacity'] > 0 else 0
                popup = f"<b>DC LINE: {dc['name']}</b><br>Flow: {dc['p_mw']:.1f} MW<br>Util: {util:.1f}%"
                folium.PolyLine(
                    coords, color='#FF6B35', weight=4, dash_array='10, 10', opacity=1, 
                    popup=popup, tooltip=f"DC Line {dc['p_mw']:.0f} MW"
                ).add_to(layer_dc_lines)

        for bus in data['buses']:
            target = layer_grid_380 if bus['vn_kv'] >= 380 else layer_grid_220
            vm_pu = bus.get('vm_pu', 1.0)
            color = self.get_voltage_status_color(vm_pu)
            
            popup = self._create_bus_popup_html(bus)
            folium.CircleMarker(
                [bus['lat'], bus['lon']], radius=4, color='#333', weight=1, 
                fill_color=color, fill_opacity=0.9, popup=folium.Popup(popup, max_width=300),
                tooltip=f"{bus['name']} ({bus['vm_pu']:.3f} pu)"
            ).add_to(target)
        
        if 'storage_units' in data:
            for s in data['storage_units']:
                self._add_storage_marker(s, layer_storage)

        if 'disconnected' in data and len(data['disconnected']) > 0:
            for db in data['disconnected']:
                folium.CircleMarker([db['lat'], db['lon']], radius=3, color='#7f8c8d', fill=True, fill_color='#7f8c8d', fill_opacity=0.6, popup=f"Disconnected: {db['name']}").add_to(layer_disc)

        self._add_aggregated_generators(data['generators'], layer_gen, layer_border, layer_inj)
        for eg in data['external_grids']:
            self._add_directional_arrow(eg, layer_border, is_slack=True)

        if 'trafos' in data:
            for t in data['trafos']:
                coords = [[t['hv_lat'], t['hv_lon']], [t['lv_lat'], t['lv_lon']]]
                popup_html = f"<b>TRAFO: {t['name']}</b><br>Load: {t['loading_percent']:.1f}%"
                folium.PolyLine(coords, color='orange', weight=3, dash_array='5, 5', opacity=0.8).add_to(layer_trafos)
                folium.CircleMarker([t['hv_lat'], t['hv_lon']], radius=4, color='orange', fill=True, fill_opacity=1.0, popup=popup_html).add_to(layer_trafos)

        if 'loads' in data:
            for l in data['loads']:
                p_val = abs(l['p_mw'])
                if p_val < 1: p_val = 1.0 
                diameter = min(50, max(14, 10 + math.log(p_val) * 4)) * 0.85
                radius = diameter / 2.0
                popup_html = f"<b>LOAD: {l['name']}</b><br>P: {l['p_mw']:.1f} MW<br>Q: {l['q_mvar']:.1f} MVar"
                folium.CircleMarker([l['lat'], l['lon']], radius=radius, color='#e74c3c', fill=True, fill_opacity=0.6, popup=popup_html, tooltip=f"Load: {l['p_mw']:.0f} MW").add_to(layer_loads)

        for l in [layer_grid_380, layer_grid_220, layer_loading, layer_gen, layer_storage, layer_loads, layer_trafos, layer_dc_lines, layer_border, layer_disc, layer_inj]: l.add_to(m)
        self._add_scenario_dashboard(m, scenario_info)
        self._add_unified_legend(m)
        folium.LayerControl(collapsed=True, position='topleft').add_to(m)
        plugins.Fullscreen(position='topleft').add_to(m)
        
        save_path = os.path.join(config.OUTPUT_DIR, scenario_name_folder, f'{scenario_name_folder}_map.html')
        m.save(save_path)
        print(f"  ✓ Visualization saved to {save_path}")

    def _add_storage_marker(self, s, layer):
        """Adds specific storage markers (Small Circle Markers)."""
        p_mw = s['p_mw']
        avail_mw = s['available_mw']
        
        if p_mw > 0.001:
            color = '#2ecc71' # Green (Discharging)
            status = "DISCHARGING"
        elif p_mw < -0.001:
            color = '#e74c3c' # Red (Charging)
            status = "CHARGING"
        else:
            color = '#95a5a6' # Grey (Idle)
            status = "IDLE"

        util = (abs(p_mw) / avail_mw * 100) if avail_mw > 0 else 0.0

        html_content = f"""
        <div style="font-family:sans-serif; font-size:12px; min-width:150px;">
            <b style="color:{color};">BATTERY: {s['name']}</b>
            <hr style="margin:4px 0;">
            <b>Status:</b> {status}<br>
            <b>Power:</b> {p_mw:+.1f} MW<br>
            <b>Capacity:</b> {avail_mw:.1f} MW<br>
            <b>Utilization:</b> {util:.1f}%
        </div>
        """
        
        folium.CircleMarker(
            [s['lat'], s['lon']],
            radius=4, 
            color='#333',
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=1.0,
            tooltip=html_content, 
            popup=folium.Popup(html_content, max_width=200)
        ).add_to(layer)

    def _add_directional_arrow(self, obj, layer, is_slack=False):
        flow = obj.get('p_mw', 0)
        if abs(flow) < 1.0: return
        is_import = flow > 0
        icon_name, color, label, desc = ('arrow-down', 'green', 'IM', 'IMPORTING') if is_import else ('arrow-up', 'blue', 'EX', 'EXPORTING')
        icon = plugins.BeautifyIcon(icon=icon_name, icon_shape='marker', border_color=color, text_color=color, number=label, inner_icon_style=f'color:{color};')
        name = obj.get('name', 'Unknown')
        type_lbl = "Main Slack" if is_slack else "Border Gen"
        folium.Marker([obj['lat'], obj['lon']], icon=icon, popup=f"<b>{name}</b><br>{type_lbl}<br>{desc}<br>Flow: {abs(flow):.1f} MW").add_to(layer)

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
                    self._add_directional_arrow(g, border_layer, is_slack=False)
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
        size = min(50, max(14, 10 + math.log(total_p)*4)) * 0.85
        icon = f'<div style="width:{size}px;height:{size}px;border-radius:50%;background:conic-gradient({", ".join(segments)});border:2px solid white;box-shadow:2px 2px 5px rgba(0,0,0,0.5);"></div>'
        popup = f"<div style='font-family:sans-serif;font-size:12px;'><b>Hub Gen: {total_p:.1f} MW</b><table>{rows}</table></div>"
        folium.Marker([lat, lon], icon=DivIcon(html=icon, icon_size=(size, size), icon_anchor=(size/2, size/2)), popup=folium.Popup(popup, max_width=300), tooltip=f"Gen Hub: {total_p:.0f} MW").add_to(layer)

    def _add_detailed_line(self, line, vn, layer, is_loading):
        coords_raw = line.get('geo_coords', None)
        coords = None
        if coords_raw:
            if isinstance(coords_raw, list): coords = coords_raw
            elif isinstance(coords_raw, str):
                try: coords = ast.literal_eval(coords_raw)
                except: pass
        if not coords: coords = [[line['from_lat'], line['from_lon']], [line['to_lat'], line['to_lon']]]

        i_max = float(line.get('max_i_ka', 0))
        i_actual = float(line.get('i_ka', 0.0)) 
        parallel = int(line.get('parallel', 1))
        
        # Total Capacity = sqrt(3) * Voltage * Current * Parallel_Circuits
        capacity_mva = math.sqrt(3) * vn * i_max * parallel if i_max > 0 else 0
        
        flow_p = float(line.get('p_from_mw', 0))
        flow_q = float(line.get('q_from_mvar', 0))
        load_pct = float(line.get('loading_percent', 0))
        
        direction = f"{line.get('from_bus_id','?')} ➝ {line.get('to_bus_id','?')}" if flow_p > 0 else f"{line.get('to_bus_id','?')} ➝ {line.get('from_bus_id','?')}"

        if parallel > 1:
            i_rating_str = f"{i_max:.2f} kA (x{parallel})"
        else:
            i_rating_str = f"{i_max:.2f} kA"
            
        html_content = f"""
        <div style="font-family:sans-serif; font-size:12px; min-width:180px;">
            <b style="color:#2c3e50;">LINE: {line['name']}</b><br>
            <span style="color:#7f8c8d;">{vn:.0f} kV | {capacity_mva:.0f} MVA (Total)</span>
            <hr style="margin:4px 0;">
            
            <b>Loading:</b> <span style="color:{'red' if load_pct>100 else 'green'}">{load_pct:.1f}%</span><br>
            <b>Current:</b> {i_actual:.2f} kA / {i_rating_str}<br>
            
            <hr style="margin:4px 0; border-top:1px dashed #ccc;">
            
            <b>Flow P:</b> {abs(flow_p):.1f} MW<br>
            <b>Flow Q:</b> {abs(flow_q):.1f} MVar<br>
            <b>Dir:</b> {direction}
        </div>
        """

        if is_loading:
            color = self.loading_colors['normal']
            if load_pct > 100: color = self.loading_colors['critical']
            elif load_pct > 80: color = self.loading_colors['high']
            elif load_pct > 60: color = self.loading_colors['elevated']
            weight = 4 + (load_pct/40)
        else:
            color = self.voltage_colors.get(vn, '#999')
            weight = 4 if vn >= 380 else 3
            
        folium.PolyLine(
            coords, color=color, weight=weight, opacity=0.8, 
            tooltip=html_content, popup=folium.Popup(html_content, max_width=200)
        ).add_to(layer)

        if is_loading:
            color = self.loading_colors['normal']
            if load_pct > 100: color = self.loading_colors['critical']
            elif load_pct > 80: color = self.loading_colors['high']
            elif load_pct > 60: color = self.loading_colors['elevated']
            weight = 4 + (load_pct/40)
        else:
            color = self.voltage_colors.get(vn, '#999')
            weight = 4 if vn >= 380 else 3
            
        folium.PolyLine(
            coords, color=color, weight=weight, opacity=0.8, 
            tooltip=html_content, popup=folium.Popup(html_content, max_width=200)
        ).add_to(layer)

    def _create_bus_popup_html(self, bus):
        vm = bus['vm_pu']
        status = "Normal"
        if vm > 1.05: status = "<span style='color:red'>HIGH (>1.05)</span>"
        elif vm < 0.95: status = "<span style='color:blue'>LOW (<0.95)</span>"
        return f"""<div style='font-family:sans-serif;font-size:12px;'>
        <div style='background:#2980b9;color:white;padding:5px;'><b>BUS: {bus['name']}</b></div>
        <table style='width:100%;margin-top:5px;'>
        <tr><td>Voltage Level</td><td style='text-align:right'>{bus['vn_kv']:.0f} kV</td></tr>
        <tr><td>Per Unit</td><td style='text-align:right'><b>{vm:.3f} pu</b></td></tr>
        <tr><td>Status</td><td style='text-align:right'>{status}</td></tr>
        <tr><td>Angle</td><td style='text-align:right'>{bus.get('va_degree', 0):.2f}°</td></tr>
        </table></div>"""

    def _map_line_voltages(self, lines, buses):
        b_v = {b['id']: b['vn_kv'] for b in buses}
        v_map = {}
        for l in lines:
            f_id = l.get('from_bus_id')
            t_id = l.get('to_bus_id')
            v1 = b_v.get(f_id, 380)
            v2 = b_v.get(t_id, 380)
            v_map[l['id']] = max(v1, v2)
        return v_map

    def _add_scenario_dashboard(self, m, info):
        cfs = info.get('gen_by_type', {})
        total = info.get('total_gen_mw', 1)
        mix = ""
        for k, v in sorted(cfs.items(), key=lambda x:x[1], reverse=True)[:8]:
            color = config.GENERATOR_TYPE_COLORS.get(k, '#333')
            mix += f"""<div style="display:flex;justify-content:space-between;margin-bottom:2px;border-bottom:1px solid #eee;">
            <span><span style="color:{color}">●</span> {k}</span><b>{v:.0f} MW</b></div>"""
        html = f"""<div id="dashboard" style="position:fixed;top:10px;right:10px;width:240px;background:rgba(255,255,255,0.95);border-left:5px solid #2980b9;padding:10px;z-index:900;font-family:sans-serif;font-size:11px;box-shadow:0 4px 10px rgba(0,0,0,0.2);">
        <h3 style="margin:0;">📊 {info['name']}</h3>
        <div style="margin:5px 0;display:grid;grid-template-columns:1fr 1fr;gap:5px;">
        <div style="background:#eafaf1;padding:5px;text-align:center;"><b style="color:#27ae60">GEN {info.get('total_gen_mw',0)/1000:.1f} GW</b></div>
        <div style="background:#fdedec;padding:5px;text-align:center;"><b style="color:#c0392b">LOAD {info.get('total_load_mw',0)/1000:.1f} GW</b></div>
        </div><div style="max-height:300px;overflow-y:auto;">{mix}</div></div>"""
        m.get_root().html.add_child(folium.Element(html))

    def _add_unified_legend(self, m):
        gen_html = "".join([f'<div style="margin-bottom:2px;"><span style="background:{c};width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px;"></span>{k}</div>' for k,c in sorted(config.GENERATOR_TYPE_COLORS.items()) if k!='default'])
        html = f"""<div style="position:fixed;bottom:20px;right:10px;width:180px;max-height:200px;overflow-y:auto;background:rgba(255,255,255,0.9);border:1px solid #ccc;border-radius:5px;padding:8px;z-index:999;font-family:sans-serif;font-size:10px;">
        <h4 style="margin:0 0 5px 0;">Legend</h4>
        <b>Voltage Status</b><br><span style="color:#e74c3c">● High (>1.05)</span><br><span style="color:#3498db">● Low (<0.95)</span><br><span style="color:#2ecc71">● Normal</span><br>
        <b>Flow Direction</b><br><span style="color:green">▼ Import</span> <span style="color:blue">▲ Export</span><br>
        <div style="margin-top:5px;"><b>Generators</b><br>{gen_html}</div></div>"""
        m.get_root().html.add_child(folium.Element(html))