from . import *

import json, traceback

from collections import defaultdict


class Node:

	_all = {}

	@classmethod
	def get(cls, search_id):
		return cls._all[str(search_id)]

	def __repr__(self):
		return f"{self.type} {self.id}, at {self.coords} conns: {self.connections if len(self.connections) < 5 else len(self.connections)}"

	def html(self):
		return f"""
		<b>{self.type}</b><br>
		WayID: <a href="https://www.openstreetmap.org/way/{self.id}" target=_blank>{self.id}</a><br>
		Location: {self.coords}<br>
		Voltages: {', '.join([f"{v // 1000}kV" for v in self.voltages])}<br>
		Transformers:
		<ul>
		{''.join([f"<li>{tf}</li>" for tf in self.transformers]) if self.type == NodeType.SUBSTATION else ''}
		</ul>
		Connections:
		<ul>
		{''.join([f"<li>{conn}</li>" for conn in self.connections])}
		</ul>
		Generators ({len(self.generators)} total):
		<ul>
		{''.join([f"<li>{gen}</li>" for gi, gen in enumerate(self.generators) if gi < 8])}
		{f"<li>{len(self.generators)-8} more...</li>" if len(self.generators) > 8 else ""}
		</ul>
		Loads:
		<ul>
		{''.join([f"<li>{load}</li>" for load in self.loads])}
		</ul>
		"""

	def __init__(self, way_id, coords, name=None, operator=None, conn_dict={}, filter_f=None):

		self.type = NodeType.UNDEF

		# There is one annoying substation with quotes encoded into the ID -.-
		# It's "way/99999111"
		if isinstance(way_id, str) and way_id[0] == '"' and way_id[-1] == '"':
			way_id = way_id[1:-1]

		if isinstance(way_id, str) and way_id[0:4] == "way/":
			self.id = int(way_id[4:])
		else:
			self.id = way_id

		# NOTE: Not sure if we we want to keep it this way but for now it's fine to use strings as IDs
		self.id = str(self.id)

		self.coords = Coords(coords)
		self.coords.round() # default precision

		self.name = name
		self.operator = operator

		self.connections = conn_dict.copy()
		self.generators = set()
		self.loads = set()

		self.region = None # NUTS id

		if filter_f and not filter_f(self):
			raise FilteredItem("Item is filtered by filter_f()")

		__class__._all[self.id] = self

	def delete(self):

		del __class__._all[self.id]

		for g in self.generators:
			del Generator._all[g]

	def add_conn(self, connection, end_type):
		self.connections[connection.id] = end_type

	def add_conns(self, connections):
		self.connections |= connections.copy()

	def add_gen(self, gen_id):
		self.generators.add(gen_id)

	def add_load(self, load_id):
		self.loads.add(load_id)

	def max_v(self):
		return max(self.voltages)

	def min_v(self):
		return min(self.voltages)

	def update_voltages_from_conns(self):

		voltages = set()
		for cid in self.connections:
			for circ in Connection.get(cid).circuits:
				voltages.add(circ.voltage)

		self.voltages = list(voltages)

		if self.type == NodeType.SUBSTATION:
			self.update_transformers()

	@classmethod
	def update_all_voltages_from_conns(cls):

		for node in cls._all.values():
			node.update_voltages_from_conns()

	def to_csv_lines(self):
		return [
			[
				f"{self.id}_{v//1000}",
				util.CSV.escape(self.name or self.id),
				str(v//1000),
				str(self.coords.lat),
				str(self.coords.lon)
			]
			for v in self.voltages
		]

	@classmethod
	def write_csv(cls, filename):

		with util.CSV(filename, ["bus_id", "name", "vn_kv", "lat", "lon"]) as csv:
			for el in cls._all.values():
				csv.print_rows(el.to_csv_lines())

		print("Wrote Node CSV to", filename)

class AlreadyExistsException(Exception):
	pass

class Branch(Node):

	def __init__(self, coords, conn_dict):

		conn_list = '_'.join(sorted(conn_dict.keys()))
		br_id = f"br_{conn_list}"
		coords.round() # default precision
		nr = 1
		while br_id in Node._all:
			if Node.get(br_id).coords == coords:
				raise AlreadyExistsException("Branch with those conns at that point already exists")
			nr += 1
			br_id = f"br_{conn_list}_{nr}"

		super().__init__(br_id, coords, conn_dict=conn_dict)

		voltages = set()
		for conn_id in conn_dict:
			voltages.update([c.voltage for c in Connection.get(conn_id).circuits])
		self.voltages = list(voltages)

		self.type = NodeType.BRANCH

class Substation(Node):

	_point_list = []
	_point_map  = defaultdict(list)
	_search_tree = None

	_deleted_subs = []

	def __init__(self, properties, filter_f=None):

		# Done before super() so the filter can see it
		self.db_voltages = [1000 * int(key[2:]) for key, exists in properties.items() if key.startswith('KV') and exists == True]
		self.db_voltages.sort()

		# The DB values don't always match the connected lines,
		# so we override self.voltages with the connected ones later.
		self.voltages = self.db_voltages.copy()

		if not self.voltages:
			raise NoVoltageError(f"No Voltages associated with substation {properties['Id']}")

		super().__init__(
			properties['Id'],
			Coords(properties['Latitude'], properties['Longitude']),
			properties['Name'],
			properties['Operator'],
			filter_f=filter_f,
		)

		# Power estimate
		# Will be improved using transformer data later
		self.power = (600 * 1e6) if self.max_v() > 200000 else 80 * 1e6

		self.transformers = []
		self.update_transformers()

		self.type = NodeType.SUBSTATION

		__class__._point_list.append(self.coords)
		__class__._point_map[self.coords].append(self.id)

	def update_transformers(self):

		for t in self.transformers:
			Transformer.get(t).delete()

		self.transformers = []

		self.voltages.sort()

		for v_lv, v_hv in zip(self.voltages[0:], self.voltages[1:]):
			t = Transformer(self.id, v_hv, v_lv)
			self.transformers.append(t.id)

	def delete(self):

		super().delete()

		__class__._point_map[self.coords].remove(self.id)
		__class__._point_list.remove(self.coords)

		__class__._deleted_subs.append(self.id)

		for t in self.transformers:
			del Transformer._all[t]

	@classmethod
	def build_search_tree(cls):

		points_as_tuples = list(map(tuple, cls._point_list))
		__class__._search_tree = KDTree(np.radians(points_as_tuples))
		print(f"Built Tree with {len(points_as_tuples)} Substation points.")

	@classmethod
	def search(cls, center_point, radius_m):

		point_rad = np.radians(center_point)
		rad_rad = radius_m / EARTH_RADIUS

		indices = cls._search_tree.query_ball_point(point_rad, rad_rad)

		#print("\nSearch tree size:", cls._search_tree.size, "found:", indices)

		neighbors_by_point = [cls._point_map[cls._point_list[i]] for i in indices]

		nodes = []
		for neighbors_at_point in neighbors_by_point:
			nodes += neighbors_at_point

		return nodes

	@classmethod
	def search_closest(cls, center_point):

		point_rad = np.radians(center_point)

		_, index = __class__._search_tree.query(point_rad)

		closest_nodes = __class__._point_map[__class__._point_list[index]]

		return closest_nodes

	@classmethod
	def load_from_json(cls, filename, filter_f=None):

		with open(filename) as f:
			raw_substations = json.load(f)

		for raw_substation in raw_substations:

			if raw_substation['Id'].startswith('way/Vir'):
				print("Virtual entry, skip")
				continue

			try:
				substation = Substation(
					raw_substation,
					filter_f=filter_f
				)

			except FilteredItem as e:
				continue

			except NoVoltageError as e:
				print(e)
				continue

			except Exception as e:
				print(e)
				print("Offending entry:", raw_substation)
				print(traceback.format_exc())
				exit()




class Transformer:

	_all = {}

	def __repr__(self):
		return f"{self.id}: {self.power//1e6:g} MVA {self.hv_v//1000}kV <-> {self.lv_v//1000}kV"

	def __init__(self, sub_id, hv_v, lv_v, power=None):

		nr = 1
		self.id = f"tr_{sub_id}_{hv_v//1000}_{lv_v//1000}_{nr}"
		while self.id in __class__._all:
			nr += 1
			self.id = f"tr_{sub_id}_{hv_v//1000}_{lv_v//1000}_{nr}"

		self.sub = sub_id
		self.hv_v = hv_v
		self.lv_v = lv_v

		self.hv_bus = f"{sub_id}_{hv_v//1000}"
		self.lv_bus = f"{sub_id}_{lv_v//1000}"

		# Power estimate from Stefan
		# QUESTION: Obtain Transformer dataset
		self.power = power or (600*1e6 if hv_v > 200000 else 80*1e6)

		__class__._all[self.id] = self

	@classmethod
	def get(cls, id):
		return cls._all[id]

	def delete(self):
		del __class__._all[self.id]

	def to_csv_line(self):
		return [
			str(len(Node.get(self.sub).transformers)), # tf count of sub
			self.id,
			self.hv_bus,
			self.lv_bus,
			f"{(self.power//1e6):g}",
			"", # tap_side
			"", # vertical_capacity
			"" # commissioning_year

		]

	@classmethod
	def write_csv(cls, filename):

		with util.CSV(filename, ["transformer_count", "transformer_id", "hv_bus_id", "lv_bus_id", "sn_mva", "tap_side", "vertical_capacity", "commissioning_year"]) as csv:
			for el in cls._all.values():
				csv.print_row(el.to_csv_line())

		print("Wrote Transformer CSV to", filename)
