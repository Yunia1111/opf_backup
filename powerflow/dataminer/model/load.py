from datetime import datetime

from . import *

class Load:

	_all = {}
	agg = 0

	@classmethod
	def get(cls, l_id):
		return cls._all[l_id]

	def __repr__(self):
		return f"Load {self.l_id}: {self.power}MW, {self.sector}, {self.substations}"

	def __init__(self, l_id, power, sector):

		self.l_id = l_id
		self.power = power
		self.sector = set()
		self.sector.add(sector)

		self.substations = set()

		__class__._all[l_id] = self

	def add_substation(self, sub_id):
		self.substations.add(sub_id)

	@classmethod
	def total_load(cls):
		total = 0
		for load in cls._all.values():
			total += load.power
		return total

	@classmethod
	def load_from_json(cls, counties_filename, large_loads_filename, scenario=None):

		with open(counties_filename) as f:
			raw_loads = json.load(f)

		current_year = scenario['year'] if scenario else datetime.today().year
		closest_year_to_scenario = 5 * round(current_year / 5)

		for raw_load in raw_loads:

			if not 'name_short' in raw_load:
				continue

			nuts_id = raw_load['name_short']

			# Only use the entries for the relevant year
			if raw_load['year'] != closest_year_to_scenario:
				continue

			power = raw_load['statistics']['year']['overall']['mean']
			sector = raw_load['sector']

			if nuts_id in cls._all:
				# BODGE! In the future, separate loads by sector at least!
				load = cls.get(nuts_id)
				load.power += power
				load.sector.add(sector)
			else:
				Load(nuts_id, power, sector)

		with open(large_loads_filename) as f:
			raw_loads = json.load(f)

		for raw_load in raw_loads:

			# Only use future entries since existing ones are already included in the county dataset
			# Also Data Centers >=20MW without Commissioning Date, those often aren't in there (according to Stefan)
			comm_year = raw_load.get('CommissioningDate')
			if not (comm_year or (raw_load.get('Type') == "Data Center" and raw_load.get("EstimatedConsumptionMax", 0) >= 20)):
				continue

			comm_year = comm_year or 2000 # for those data centers

			# Only everything up to the scenario year
			if scenario and int(comm_year) > scenario['year']:
				continue

			if 'PowerCapacity' in raw_load and raw_load['PowerCapacity']:
				power = raw_load['PowerCapacity']

			elif 'EstimatedConsumptionMin' in raw_load and 'EstimatedConsumptionMax' in raw_load:
				power = (raw_load['EstimatedConsumptionMin'] + raw_load['EstimatedConsumptionMax']) / 2

			else:
				print("No power data in NEP load. offending:", raw_load)
				continue

			sector = raw_load['Type']

			l = Load('nep_'+raw_load['_id']['$oid'], power, sector)

			sub_ids = Substation.search_closest(Coords(raw_load['Lat'], raw_load['Long']))

			l.add_substation(sub_ids[0])

	def to_csv_lines(self):
		__class__.agg += self.power if len(self.substations) > 0 else 0
		return [
			[
				f"{sub_id}_{Node.get(sub_id).min_v()//1000}",
				str(self.power / len(self.substations)),
				str(0), # No q yet
				f"NEP load {self.l_id}" if self.l_id.startswith('nep_') else f"NUTS {self.l_id} full year all-week mean",
				util.CSV.escape('+'.join(list(self.sector))) # MAYBE: Split by sector
			]
			for sub_id in self.substations
		]

	@classmethod
	def write_csv(cls, filename):

		with util.CSV(filename, ["bus_id", "p_mw", "q_mvar", "load_name", "load_type"]) as csv:
			for el in cls._all.values():
				csv.print_rows(el.to_csv_lines())

		print("Wrote Load CSV to", filename)
