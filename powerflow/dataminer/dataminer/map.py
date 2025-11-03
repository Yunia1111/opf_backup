"""
@author: timon, oskar
"""

import folium
from folium.plugins import MeasureControl

from .model import NodeType, ConnType

def create_map(nodes, connections, generators, filename, additional_points=[]):

	print(f"Building HTML map...")

	germany_center = [52.5173, 13.3138]
	fmap = folium.Map(location=germany_center, zoom_start=16)

	for i, node in enumerate(nodes):

		print(f"Node {i:>5}/{len(nodes)}", end='\r')

		color = "purple" if node.type == NodeType.SUBSTATION else "blue"

		folium.CircleMarker(
			location=tuple(node.coords),
			radius=6,
			color=color,
			fill=True,
			fill_color=color,
			fill_opacity=0.7,
			tooltip=f"{node.type} {node.id}",
			popup=node.html(),
		).add_to(fmap)

		# MAYBE: Draw small connecting lines between subs and conn ends

	print("")

	for i, gen in enumerate(generators):

		print(f"Gen  {i:>5}/{len(generators)}", end='\r')

		color = "green"

		folium.CircleMarker(
			location=tuple(gen.coords),
			radius=6,
			color=color,
			fill=True,
			fill_color=color,
			fill_opacity=0.7,
			tooltip=f"Generator {gen.mastr_nr}",
			popup=gen.html(),
		).add_to(fmap)

	print("")

	for point in additional_points:
		color = "black"
		folium.CircleMarker(
			location=tuple(point),
			radius=6,
			color=color,
			fill=True,
			fill_color=color,
			fill_opacity=0.7,
			tooltip="additional point"
		).add_to(fmap)

	for i, conn in enumerate(connections):

		print(f"Conn {i:>5}/{len(connections)}", end='\r')

		v = max([c.voltage for c in conn.circuits])
		color = "red" if v > 200000 else "blue"
		color = "orange" if conn.type in [ConnType.HVDC_LINE, ConnType.HVDC_CABLE] else color

		# MAYBE: Thicken on Hover would be nice to see conn ends
		# There only seems to be a built in option for this for GeoJSON
		# Not for PolyLine. We can either add custom JS or figure out GeoJSON
		# Maybe check how they do it on Blindleister

		folium.PolyLine(
			conn.geometry,
			color=color,
			weight=2,
			opacity=0.8,
			tooltip=f"{conn.type} {conn.id}",
			popup=conn.html(),
		).add_to(fmap)

	fmap.add_child(MeasureControl())

	print("\nSaving...")
	fmap.save(filename)
	print(f"Saved map as '{filename}'.")

	return fmap
