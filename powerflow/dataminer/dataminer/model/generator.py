from . import *

import geopandas
from shapely.geometry import Point
from datetime import datetime
from collections import defaultdict

class Generator:

	_all = {}

	_gen_loc_sub_map = {}

	def html(self):
		return f"""
		<b>Generator</b><br>
		Mastr Nr.: {self.mastr_nr}<br>
		Name: {self.name}<br>
		Type: {self.type}<br>
		Location: {self.coords}<br>
		Voltage: {self.voltage}<br>
		Power: {self.power}<br>
		Commissioning Year: {self.comm_year}<br>
		Substation: {self.sub}<br>
		"""

	def __init__(self, gen_id, power, gen_type, sub_id=None, coords=None, comm_year=0, name=None):

		self.id = gen_id
		self.coords = coords
		self.power = power
		self.type = gen_type
		self.comm_year = comm_year
		self.name = name or gen_id

		if sub_id:
			self.sub = sub_id

		elif coords:
			closest_subs = Substation.search_closest(self.coords)
			if len(closest_subs) != 1:
				print("Multiple subs near gen:", closest_subs)

			self.sub = closest_subs[0]

		else:
			raise Exception("Either sub_id or coords must be given")

		sub = Substation.get(self.sub)
		sub.add_gen(self.id)

		# XHV/HV threshold 100MW (from Stefan)
		if self.power > 100e6:
			self.voltage = 220000 if 220000 in sub.voltages else sub.max_v()
		else:
			self.voltage = 110000 if 110000 in sub.voltages else sub.min_v()

		__class__._all[self.id] = self

	@classmethod
	def load_sub_grid_locs(cls, filename):

		with open(filename) as f:
			raw_sgls = json.load(f)

		for raw_sgl in raw_sgls:
			sub_id = raw_sgl['Id'][4:]
			for sel_id in raw_sgl['GridLocation']:
				__class__._gen_loc_sub_map[sel_id] = sub_id

	@classmethod
	def pre_process_json_cache(cls, filename, cachefilename, locfilename, oceans_file=None):

		if oceans_file:
			ocean_gpd = geopandas.read_file(oceans_file)

		__class__.load_sub_grid_locs(locfilename)

		aggregates = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

		with open(filename, 'r', encoding='utf-8') as file:

			i = 0
			for line in file:

				# strip newline and comma
				raw_generator = json.loads(line.rstrip())

				if raw_generator["UnitOperationalStatus"] == "in planning":
					# NOTE: Skip future for now
					continue

				gen_type = raw_generator["EnergySource"]
				if oceans_file and gen_type == "wind":
					shp_point = Point(coords.lon, coords.lat)
					in_water = ocean_gpd.contains(shp_point).any()
					gen_type = "wind_offshore" if in_water else "wind_onshore"

				comm_year = 0
				if "CommissionDate" in raw_generator:
					if isinstance(raw_generator["CommissionDate"]["$date"], str):
						comm_year = int(raw_generator["CommissionDate"]["$date"][0:4])
					elif isinstance(raw_generator["CommissionDate"]["$date"], dict):
						ms_timestamp = int(raw_generator["CommissionDate"]["$date"]["$numberLong"])
						comm_year = datetime.utcfromtimestamp(ms_timestamp/1000).year

				coords = Coords(raw_generator["Latitude"], raw_generator["Longitude"])

				power = raw_generator["GrossPower"] * 1000

				sel_nr = raw_generator.get("LocationMaStRNumber")
				if False and sel_nr and sel_nr in __class__._gen_loc_sub_map:
					# DEACTIVATED, contains dead references to delted subs
					# TODO: work on not deleting them ^^
					sub_id = __class__._gen_loc_sub_map[sel_nr]

				else:
					# TODO: For offshore wind, it's important to connect to
					# branch points as well. Make sure that's possible
					closest_subs = Substation.search_closest(coords)
					if len(closest_subs) != 1:
						print("Multiple subs near gen:", closest_subs)

					sub_id = closest_subs[0]

				aggregates[sub_id][gen_type][comm_year] += power

				i += 1
				if i % 200 == 0:
					print(f"Loaded {i:>7}/~6421481 gens", end='\r')

			print("")

		with open(cachefilename, 'w+') as f:
			json.dump(aggregates, f, indent=2)

	@classmethod
	def load_from_json(cls, cachefilename, oceans_file=None):

		with open(cachefilename) as f:
			substation_aggregates = json.load(f)

		for sub_id in substation_aggregates:

			for gen_type in substation_aggregates[sub_id]:

				power_by_years = substation_aggregates[sub_id][gen_type]
				for comm_year in power_by_years:

					gen_id = f"gen_{sub_id}_{gen_type}_{comm_year}"

					Generator(
						gen_id,
						power_by_years[comm_year],
						gen_type,
						sub_id,
						coords=None,
						comm_year=comm_year
					)

	def to_csv_line(self):
		return [
			f"{self.sub}_{self.voltage//1000}",
			util.CSV.escape(self.name),
			str(self.power / 1e6),
			str(1),
			str(self.power / 1e6),
			str(self.type),
			str(self.comm_year)
		]

	@classmethod
	def write_csv(cls, filename):

		with util.CSV(filename, ["bus_id", "generator_name", "p_mw", "vm_pu", "sn_mva", "generation_type", "commissioning_year"]) as csv:
			for i,el in enumerate(cls._all.values()):
				csv.print_row(el.to_csv_line())
				if i % 100 == 0:
					print(f"Wrote {i:>7}/{len(cls._all)} gens", end='\r')
			print("")

		print("Wrote Generator CSV to", filename)
