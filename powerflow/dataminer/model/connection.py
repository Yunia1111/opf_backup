from . import *

import re, json, traceback

from collections import defaultdict




class PowerFrequencyError(ValueError):
	def __init__(self, message, frequency):
		super().__init__(message)
		self.frequency = frequency

class CablesPerPhaseError(ValueError):
	pass

class DivisibilityError(ValueError):
	pass

class NoValidCircuitError(ValueError):
	pass

class CircuitCountError(ValueError):
	pass




class WireType:

	# Use ampacities from adjacient cables if missing

	conn_types = {
		"243-AL1/39-ST1A 110.0": {
			"r_ohm_per_km": 0.1188,
			"x_ohm_per_km": 0.39,
			"c_nf_per_km": 9,
			"max_i_ka": 0.645
		},
		"490-AL1/64-ST1A 220.0": {
			"r_ohm_per_km": 0.059,
			"x_ohm_per_km": 0.285,
			"c_nf_per_km": 10,
			"max_i_ka": 0.96
		},
		"490-AL1/64-ST1A 380.0": {
			"r_ohm_per_km": 0.059,
			"x_ohm_per_km": 0.253,
			"c_nf_per_km": 11,
			"max_i_ka": 0.96
		},
		"N2XS(FL)2Y 1x240 RM/35 64/110 kV": {
			"r_ohm_per_km": 0.075,
			"x_ohm_per_km": 0.149,
			"c_nf_per_km": 135,
			"max_i_ka": 0.526
		},
		"XLPE 1×1600 Cu 220 (rough)": {
			"r_ohm_per_km": 0.012,
			"x_ohm_per_km": 0.12,
			"c_nf_per_km": 210,
			"max_i_ka": 1.3,
		},
		"XLPE 1x2500 Cu 380 (rough)": {
			"r_ohm_per_km": 0.009,
			"x_ohm_per_km": 0.11,
			"c_nf_per_km": 230,
			"max_i_ka": 2.0,
		}
	}

	def __init__(self, conn_type, voltage, ampacity_per_system=None):

		if ampacity_per_system:

			# TODO: Build a config system+module for this stuff
			with open("data/source_data/wires.json") as f:
				wire_types = json.load(f)

			wire_types = wire_types["lines" if conn_type == ConnType.LINE else "cables"]
			wire_types = wire_types[str(voltage)] # TODO: Handle nonexistant, e.g. 110

			ampacity_key = "max_i_ka_air" if conn_type == ConnType.LINE else "max_i_ka_ground"

			ampacity_per_system_kA = ampacity_per_system / 1000

			name = None
			data = None
			for n, d in wire_types.items():
				# NOTE: Wire type lists are sorted, so this works. Keep them sorted.
				name = n
				data = d
				if d[ampacity_key] > ampacity_per_system_kA:
					break

		else:

			if voltage < 150000:
				name = "243-AL1/39-ST1A 110.0" if conn_type == ConnType.LINE else "N2XS(FL)2Y 1x240 RM/35 64/110 kV"
			elif voltage < 250000:
				name = "490-AL1/64-ST1A 220.0" if conn_type == ConnType.LINE else "XLPE 1×1600 Cu 220 (rough)"
			else:
				name = "490-AL1/64-ST1A 380.0" if conn_type == ConnType.LINE else "XLPE 1x2500 Cu 380 (rough)"

			data = __class__.conn_types[name]

			ampacity_per_system_kA = data["max_i_ka"]


		self.name = name

		self.r_ohm_per_km = data["r_ohm_per_km"]
		self.x_ohm_per_km = data["x_ohm_per_km"]
		self.c_nf_per_km  = data["c_nf_per_km"]
		self.max_i_ka     = round(ampacity_per_system_kA, 3)




class Circuit:

	def __init__(self, voltage, frequency, phases, cables, wire_type):

		self.voltage   	= voltage
		self.frequency 	= frequency
		self.phases    	= phases
		self.cables    	= cables
		self.wire_type  = wire_type

		if (cables % phases) != 0:
			raise CablesPerPhaseError(f"Circuit: cable ({cables}) and phase ({phases}) count don't match.")

		self.systems = cables // phases

		self.capacity = None
		self.ampacity = None
		self.dlr = None

	def __repr__(self):
		return f"{self.voltage//1000}kV {self.phases} phase, {self.cables} cables, {self.systems} systems, {self.capacity}MVA, {self.ampacity}A, DLR: {self.dlr}A, Wire:{self.wire_type.name}"

	def max_v(self):
		return self.voltage



class Connection:

	_all = {}
	connpoint_list = []
	connpoint_map  = defaultdict(dict)

	f2p = {
		50: 3,
		16.7: 2,
		16.67: 2,
		0.0: 1,
	}

	_deleted_conns = []

	@classmethod
	def get(cls, search_id):
		return cls._all[str(search_id)]

	def debug(self, *args, **kwargs):
		if self.interesting:
			print(*args, **kwargs)

	def __repr__(self):
		return f"{self.type} {self.id}, {len(self.circuits)} circuits, {int(self.length)}m, {self.operator}"

	def html(self):
		return f"""
		<div style="width:420px;text-align:center">
			<b>{self.type}</b>
		</div>
		WayID: <a href="https://www.openstreetmap.org/way/{self.id}" target=_blank>{self.id}</a><br>
		Circuits: {len(self.circuits)}
		<ul>
		{''.join([f"<li>{circuit}</li>" for circuit in self.circuits])}
		</ul>
		Voltages: {', '.join([f"{c.voltage // 1000}kV" for c in self.circuits])}<br>
		Length: {int(self.length)}m<br>
		Operator: {self.operator}<br>
		Start Node: {self.startNode}<br>
		End Node: {self.endNode}<br>
		"""

	def __init__(self, way_id, type, voltages, capacities, ampacities, dlr, frequency, circuits, cables, operator, geometry, length=None, startNode=None, endNode=None, filter_f=None):

		self.type = type or ConnType.UNDEF

		if isinstance(way_id, str) and way_id[0:4] == "way/":
			self.id = int(way_id[4:])
		else:
			self.id = way_id

		# NOTE: Not sure if we we want to keep it this way but for now it's fine to use strings as IDs
		self.id = str(self.id)

		self.interesting = False

		if len(voltages) < 1:
			raise NoVoltageError(f"No Voltages given, can't use conn {self.id}")

		# filter rail power voltage because it's often not given and we
		# standardized on only listing 3-phase grid voltages here.
		# It's important for assigning voltages to circuits later.
		voltages = [v for v in voltages if v != 15000]

		#Currently not filtering unused voltages because it messes with the algorithm
		for v in voltages:
			if v not in [380000, 220000, 110000]:
				#voltages.remove(v)
				#self.interesting = True
				self.debug(f"Unknown Voltage: {v}V")

		if len(voltages) < 1:
			raise NoVoltageError(f"No relevant voltages given")

		# Assume 50Hz if not given
		frequencies = re.split('[;,]', frequency) if frequency else ['50']
		frequencies = [float(f) for f in frequencies]

		cables_list   = [int(c) for c in re.split('[;,]',   cables)] if cables   else []
		circuits_list = [int(c) for c in re.split('[;,]', circuits)] if circuits else []

		if len(frequencies) > 1 or len(cables_list) > 1 or len(circuits_list) > 1:
			self.interesting = True
			self.debug("Mixed lines")

		cables   = sum(  cables_list)
		circuits = sum(circuits_list)

		if circuits and len(cables_list) > circuits:
			raise CircuitCountError("Number of elements in cable list larger than circuit count")

		# Determine HVDC
		if frequency == '0':

			# '0' might be an erroneous entry. In that case, convert to 3-phase 50Hz.
			if (cables // (circuits or 1)) == 3 and any([v in [110000, 220000, 380000] for v in voltages]):
				frequency = '50'
				frequencies = [50.0]

			# Otherwise, assume HVDC
			else:
				self.type = ConnType.HVDC_LINE if type == ConnType.LINE else ConnType.HVDC_CABLE


		# Try determining circuit distribution across voltages from cable distribution if given
		# Example: 67b04fd725fabcec747df2f1 (Cables 9;3, Circuits: 4 -> Should be Circuits: 3;1)
		if len(cables_list) > 1 and len(circuits_list) <= 1:
			self.interesting = True
			_c_circuits_list = [cc // 3 for cc in cables_list if cc % 3 == 0]
			if sum(_c_circuits_list) >= circuits and len(_c_circuits_list) == len(cables_list):
				circuits_list = _c_circuits_list
				circuits = sum(circuits_list)
			elif not circuits:
				circuits = len(cables_list)
			else:
				self.debug("Cable list does not match 3-phase circuits")

		# Assume 3-phase for missing values
		if cables:
			circuits = circuits if circuits else cables // 3
		elif circuits:
			cables = cables if cables else circuits * 3
		else:
			circuits = 1
			cables = 3

		circuits_list = circuits_list if circuits_list else [circuits]

		num_circuits = max(circuits, len(voltages), len(frequencies))

		if circuits != 0 and num_circuits % circuits != 0:
			self.interesting = True
			self.debug("num_circuits % circuits != 0 -> Someting isn't right!!!")
			self.debug("Offending:", self.id)
			# NOTE: This only happens with one entry:
			# 67b04fd725fabcec747e04b5 / way/113547739
			# It has 3 Voltages, but is listed with 2 Circuits
			# Checking OIM, it is clear that 3 circuits is correct
			# This is handled correcly by the num_circuits line above

		if num_circuits % len(voltages) != 0:
			#self.interesting = True
			self.debug("num_circuits % len(voltages) != 0")

		if num_circuits % len(frequencies) != 0:
			#self.interesting = True
			self.debug("num_circuits % len(frequencies) != 0")

		if cables % num_circuits != 0:
			self.interesting = True
			self.debug("cables % num_circuits != 0")

		self.circuits = []
		remaining_cables = cables
		remaining_circuits = num_circuits
		vi = 0
		fi = 0

		# maps circuit index to voltage index if multiple circuit counts are given
		if len(circuits_list) > 1:
			self.interesting = True
			ci2vi = sum([[i]*cc for i,cc in enumerate(circuits_list)], [])
			self.debug("ci2vi:", ci2vi)

		remaining_circuits_by_f = {f: circuits_list[i % len(circuits_list)] for i,f in enumerate(frequencies)}

		unused_frequencies = frequencies.copy()

		while remaining_circuits > 0:

			self.debug("Remaining: ", remaining_cables, remaining_circuits, end=" -> ")

			if remaining_cables <= 0:
				self.interesting = True
				self.debug("Not enough cables for all circuits")
				#raise CircuitCountError("Not enough cables for all circuits")

			f = -1

			if (remaining_cables % 3 == 0 and remaining_cables % 2 == 0):

				if len(circuits_list) > 1 and len(frequencies) > 1:
					# frequency with most remaining circuits
					f = max(remaining_circuits_by_f, key=remaining_circuits_by_f.get)
				else:
					# Round robin of unused
					#print(unused_frequencies)
					flist = unused_frequencies if unused_frequencies else frequencies
					f = flist[fi % len(flist)]
					fi += 1

			elif (50 in frequencies) and (remaining_cables % 3 == 0 or remaining_cables % 2 != 0):

				f = 50

			elif (0 in frequencies):

				f = 0

			elif (not frequency) and (remaining_cables % 2 == 0):

				# Assume railway power if grid power doesn't fit
				f = 16.7

			elif any([0 < f < 50 for f in frequencies]) and (remaining_cables % 2 == 0):

				f = next(f for f in (frequencies) if 0 < f < 50)

			else:

				# Stefan says to just drop one wire because it's probably an earth wire? Eh, okay.
				if (remaining_cables - 1) % 3 == 0:

					remaining_cables -= 1
					self.interesting = True
					self.debug("Dropping potential earth wire")
					continue


				# catch remaining. Shouldn't happen i think
				raise PowerFrequencyError("Can't decide circuit frequency", frequency)


			phases = self.f2p[f]

			self.debug(f"chose {phases}-phase", end=", ")

			if f in unused_frequencies:
				unused_frequencies.remove(f)

			if f in remaining_circuits_by_f:
				remaining_circuits_by_f[f] -= 1

			if phases in [3, 1]:

				# Round robin if no circuit separation given (most times)
				# Assumes equal distribution of voltages across circuits
				idx = ci2vi[vi] if len(circuits_list) > 1 else vi
				voltage = voltages[idx % len(voltages)]
				vi += 1

			else:

				voltage = 15000

			# cpp is "cables per phase"
			max_cpp_for_type = remaining_cables // phases
			target_cpp = round(max_cpp_for_type / remaining_circuits)

			# If it's explicitly defined how many circuits (here =cpp) per
			# freq/voltage then we only use that amount
			if len(circuits_list) > 1 and len(frequencies) > 1:
				target_cpp = min(target_cpp, circuits_list[frequencies.index(f)])

			c_cables = max(phases, phases * target_cpp)

			self.debug("using", c_cables, "cables")

			c = Circuit(
				voltage,
				f,
				phases,
				c_cables,
				WireType(self.type, voltage)
			)

			if filter_f and filter_f(c):
				self.circuits.append(c)

			remaining_cables -= c_cables
			remaining_circuits -= 1

		if len(self.circuits) < 1:
			raise NoValidCircuitError("No valid circuits found in this conn")

		for capacity_voltage, capacity in capacities.items():

			voltage_systems = 0
			for c in self.circuits:
				if c.voltage == capacity_voltage:
					voltage_systems += c.systems

			if voltage_systems == 0:
				continue

			capacity_per_system = capacity / voltage_systems # is in MVA

			ampacity = ampacities.get(capacity_voltage) or (capacity * 1000000 / capacity_voltage) # in A

			ampacity_per_system = ampacity / voltage_systems # in A

			dlr_per_system = tuple([val/voltage_systems for val in dlr.get(capacity_voltage, (0, 0))])

			for c in self.circuits:

				if c.voltage == capacity_voltage:

					c.capacity = capacity_per_system * c.systems
					c.ampacity = ampacity_per_system * c.systems
					c.dlr = (dlr_per_system[0] * c.systems, dlr_per_system[1] * c.systems)

					c.wire_type = WireType(self.type, c.voltage, ampacity_per_system)


		self.operator = operator

		self.length = length if length else util.Geo.compute_length(geometry)

		# Dataset is (lon,lat) for some reason, flip that
		self.geometry = [(lat, lon) for lon, lat in geometry]

		self.startNode = startNode
		self.endNode = endNode

		if filter_f and not filter_f(self):
			raise FilteredItem("Item is filtered by filter_f()")

		__class__._all[self.id] = self

		self.startPoint = Coords(self.geometry[0])
		__class__.connpoint_list.append(self.startPoint)
		__class__.connpoint_map[self.startPoint][self.id] = EndType.START

		self.endPoint = Coords(self.geometry[-1])
		__class__.connpoint_list.append(self.endPoint)
		__class__.connpoint_map[self.endPoint][self.id] = EndType.END

	def delete(self):

		__class__._deleted_conns.append(f"way/{self.id}")

		del __class__._all[self.id]

		del __class__.connpoint_map[self.startPoint][self.id]
		__class__.connpoint_list.remove(self.startPoint)

		del __class__.connpoint_map[self.endPoint][self.id]
		__class__.connpoint_list.remove(self.endPoint)

	@classmethod
	def build_search_tree(cls):

		points_as_tuples = list(map(tuple, cls.connpoint_list))
		__class__._search_tree = KDTree(np.radians(points_as_tuples))
		print(f"Built Tree with {len(points_as_tuples)} Node points.")

	@classmethod
	def search(cls, center_point, radius_m, exclude_idx=None):

		point_rad = np.radians(center_point)
		rad_rad = radius_m / EARTH_RADIUS

		indices = cls._search_tree.query_ball_point(point_rad, rad_rad)

		#print("\nSearch tree size:", cls._search_tree.size, "found:", indices)

		neighbors_by_point = [cls.connpoint_map[cls.connpoint_list[i]] for i in indices if i != exclude_idx]

		if not neighbors_by_point:
			return None

		#nodes = []
		#for neighbors_at_point in neighbors_by_point:
		#	nodes += neighbors_at_point

		conns = dict()
		# All conns associated with the current point
		conns |= cls.connpoint_map[center_point].copy()
		# All nearby conns
		for neighbor_point_conns in neighbors_by_point:
			conns |= neighbor_point_conns.copy()

		return conns

	def max_v(self):
		return max([c.voltage for c in self.circuits])

	@classmethod
	def test_refs(cls, node_ids):

		unfound_buses = set()

		for conn in cls._all.values():

			if conn.startNode not in node_ids:
				unfound_buses.add(conn.startNode)

			if conn.endNode not in node_ids:
				unfound_buses.add(conn.endNode)

		return unfound_buses

	def to_csv_lines(self):
		#from_bus_id,to_bus_id,length_km,r_ohm_per_km,x_ohm_per_km,c_nf_per_km,max_i_ka,name
		return [
			[
				f"{self.startNode}_{c.voltage//1000}",
				f"{self.endNode}_{c.voltage//1000}",
				str(max(round(self.length / 1000,3), 0.05)), # at least 50m
				str(c.wire_type.r_ohm_per_km),
				str(c.wire_type.x_ohm_per_km),
				str(c.wire_type.c_nf_per_km),
				str(c.wire_type.max_i_ka),
				str(c.capacity if c.capacity else ""),
				str(c.dlr[0] if c.dlr and c.dlr[0] else ""),
				str(c.dlr[1] if c.dlr and c.dlr[1] else ""),
				f"way/{self.id}",
				str(c.systems), # parallel_cables
				"overhead" if self.type == ConnType.LINE else "underground", # line_type
				"AC" if c.frequency > 0 else "DC", # ac_dc_type
				"", # switch_group
				"", # commissioning_year
				json.dumps(self.geometry) # geographic_coordinates
			]
			for c in self.circuits if (self.startNode and self.endNode)
		]

	def to_wiredata_csv_lines(self):
		return [
			[
				str(max(round(self.length / 1000,3), 0.05)), # at least 50m
				str(c.wire_type.r_ohm_per_km),
				str(c.wire_type.x_ohm_per_km),
				str(c.wire_type.c_nf_per_km),
				str(c.wire_type.max_i_ka),
				str(c.systems),
				str(c.voltage // 1000),
				str(c.frequency)
			]
			for c in self.circuits if (self.startNode and self.endNode)
		]

	@classmethod
	def write_csv(cls, filename, wiredata_filename, node_getter):

		with util.CSV(filename, [
			"from_bus_id",
			"to_bus_id",
			"length_km",
			"r_ohm_per_km",
			"x_ohm_per_km",
			"c_nf_per_km",
			"max_i_ka",
			"capacity_mva",
			"dlr_min_a",
			"dlr_max_a",
			"name",
			"parallel_cables_per_phase",
			"line_type",
			"ac_dc_type",
			"switch_group",
			"commissioning_year",
			"geographic_coordinates"
		]) as csv, util.CSV(wiredata_filename, [
			"line_way_id",
			"from_way_id",
			"to_way_id",
			"length_km",
			"r_ohm_per_km",
			"x_ohm_per_km",
			"c_nf_per_km",
			"max_i_ka",
			"parallel_cables_per_phase",
			"voltage_kV",
			"frequency"
		]) as wiredata_csv:

			for el in cls._all.values():

				csv.print_rows(el.to_csv_lines())

				line_way_id = f"way/{el.id}"
				from_way_id = to_way_id = ""
				if el.startNode and el.endNode:
					from_way_id = node_getter(el.startNode).id or ""
					to_way_id = node_getter(el.endNode).id or ""

				wiredata_csv.print_rows([
					([line_way_id, from_way_id, to_way_id] + line)
					for line in el.to_wiredata_csv_lines()
				 ])

		print("Wrote Connection and Wiredata CSVs to", filename)




class TransmissionLine(Connection):

	def __init__(self, properties, geometry, filter_f=None):

		""" SAMPLE:

		'properties': {
			'Id': 184010752,
			'Cables': '18',
			'Circuits': '6',
			'Frequency': None,
			'Location': None,
			'Operator':
			'Amprion;Westnetz',
			'Element': 'line',
			'Rating': 7,
			'Voltage_1': 380000, 'Voltage_2': 380000,
			'Voltage_3': 220000,
			'Voltage_4': 110000, 'Voltage_5': 110000, 'Voltage_6': 110000
		},
		'geometry': [
			[7.8978644, 52.2815035],
			[7.8992987, 52.2851929],
			[7.9007042, 52.2890248],
			[7.9022706, 52.2930869],
			[7.9034105, 52.2959798],
			[7.9045773, 52.2989725],
			[7.9038906, 52.3031387]
		]
		"""

		voltages = [voltage for key, voltage in properties.items() if key.startswith('Voltage_') and voltage]
		capacities = {int(key[15:])*1000: capacity for key, capacity in properties.items() if key.startswith('Rated_Capacity_') and capacity}

		ampacities = {int(key[21:24])*1000: ampacity for key, ampacity in properties.items() if key.startswith('Maximum_Current_Imax_') and ampacity}
		dlr_min = {int(key[8:11])*1000: ampacity for key, ampacity in properties.items() if key.startswith('DLR_Min_') and ampacity}
		dlr_max = {int(key[8:11])*1000: ampacity for key, ampacity in properties.items() if key.startswith('DLR_Max_') and ampacity and not key.startswith("DLR_Max_C")}
		dlr = {voltage: (dlr_min[voltage], dlr_max[voltage]) for voltage in dlr_min.keys()}

		super().__init__(
			way_id = properties['Id'],
			type = ConnType.LINE,
			voltages = voltages,
			capacities = capacities,
			ampacities = ampacities,
			dlr = dlr,
			frequency = properties['Frequency'],
			circuits = properties['Circuits'],
			cables = properties['Cables'],
			operator = properties['Operator'],
			geometry = geometry,
			filter_f = filter_f,
		)

	@classmethod
	def load_from_json(cls, filename, filter_f=None):

		with open(filename) as f:
			raw_lines = json.load(f)

		for raw_line in raw_lines:

			try:

				line = TransmissionLine(
					raw_line['properties'],
					raw_line['geometry'],
					filter_f=filter_f
				)

				#if line.interesting:
				#
				#	print("Interesting:", raw_line)
				#
				#	print("Circuits:")
				#	for c in line.circuits:
				#		print(c)
				#
				#	input("Press Enter to continue...")

			except FilteredItem as e:
				continue

			except NoValidCircuitError as e:
				print(e)
				continue

			except NoVoltageError as e:
				print(e)
				continue

			except PowerFrequencyError as e:
				# 67b04fd825fabcec747e1fae
				print(raw_line)
				print(e)
				#print("Offending entry:", raw_line)
				#input("Press Enter to continue...")
				continue

			except CircuitCountError as e:
				# 1445957438 -> Cables: '1;4', Circuits: '1'
				print(raw_line)
				print(e)
				if (raw_line['properties']['Id'] == 1445957438):
					continue
				else:
					exit()

			except Exception as e:
				print(e)
				print("Offending entry:", raw_line)
				print(traceback.format_exc())
				exit()




class TransmissionCable(Connection):

	def __init__(self, properties, geometry, filter_f=None):

		""" SAMPLE:

		'properties': {
			'Id': 26593932,
			'Cables': '6',
			'Circuits': '2',
			'Frequency': '50',
			'Location': 'underground',
			'Operator': 'RWE',
			'Element': 'cable',
			'Rating': 7,
			'Voltage_1': 110000,
			'Confidence': 94
		},
		'geometry': [
			[6.4543023, 50.8697615],
			[6.4529849, 50.8699216],
			[6.4516886, 50.87147],
			[6.4507093, 50.8733219]
		]
		"""

		voltages = [voltage for key, voltage in properties.items() if key.startswith('Voltage_') and voltage]
		capacities = {int(key[15:])*1000: capacity for key, capacity in properties.items() if key.startswith('Rated_Capacity_') and capacity}

		ampacities = {int(key[21:24])*1000: ampacity for key, ampacity in properties.items() if key.startswith('Maximum_Current_Imax_') and ampacity}
		dlr_min = {int(key[8:11])*1000: ampacity for key, ampacity in properties.items() if key.startswith('DLR_Min_') and ampacity}
		dlr_max = {int(key[8:11])*1000: ampacity for key, ampacity in properties.items() if key.startswith('DLR_Max_') and ampacity and not key.startswith("DLR_Max_C")}
		dlr = {voltage: (dlr_min[voltage], dlr_max[voltage]) for voltage in dlr_min.keys()}

		super().__init__(
			way_id = properties['Id'],
			type = ConnType.CABLE,
			voltages = voltages,
			capacities = capacities,
			ampacities = ampacities,
			dlr = dlr,
			frequency = properties['Frequency'],
			circuits = properties['Circuits'],
			cables = properties['Cables'],
			operator = properties['Operator'],
			geometry = geometry,
			filter_f = filter_f,
		)

	@classmethod
	def load_from_json(cls, filename, filter_f=None):

		with open(filename) as f:
			raw_cables = json.load(f)

		for raw_cable in raw_cables:

			try:

				cable = TransmissionCable(
					raw_cable['properties'],
					raw_cable['geometry'],
					filter_f=filter_f
				)

				#if cable.interesting:
				#
				#	print("Interesting:", raw_cable)
				#
				#	print("Circuits:")
				#	for c in cable.circuits:
				#		print(c)
				#
				#	input("Press Enter to continue...")

			except FilteredItem as e:
				continue

			except NoValidCircuitError as e:
				print(e)
				continue

			except NoVoltageError as e:
				print(e)
				continue

			except PowerFrequencyError as e:
				print(raw_cable)
				print(e)
				#print("Offending entry:", raw_cable)
				#input("Press Enter to continue...")
				continue

			except Exception as e:

				if raw_cable['properties']['Id'] == 378369401 and raw_cable['properties']['Cables'] == "3w":
					continue # Dataset typo i think

				print(e)
				print("Offending entry:", raw_cable)
				print(traceback.format_exc())
				exit()
