from datetime import datetime

from . import *

class Load:

	_all = {}
	agg = 0

	@classmethod
	def get(cls, nuts_id):
		return cls._all[nuts_id]

	def __init__(self, nuts_id, power, sector):

		self.nuts_id = nuts_id
		self.power = power
		self.sector = set()
		self.sector.add(sector)

		self.substations = set()

		__class__._all[nuts_id] = self

	def add_substation(self, sub_id):
		self.substations.add(sub_id)

	@classmethod
	def total_load(cls):
		total = 0
		for load in cls._all.values():
			total += load.power
		return total

	# TODO: Add loads from loads collection that aren't commisioned yet (big load additions)

	@classmethod
	def load_from_json(cls, filename, scenario=None):

		with open(filename) as f:
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

	def to_csv_lines(self):
		__class__.agg += self.power if len(self.substations) > 0 else 0
		return [
			[
				f"{sub_id}_{Node.get(sub_id).min_v()//1000}",
				str(self.power / len(self.substations)),
				str(0), # No q yet
				f"NUTS {self.nuts_id} full year all-week mean",
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
