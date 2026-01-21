def fetch_db(scenario=None):

	from .db import DB

	db = DB()
	db.fetch_data([
		"substations",
		"transmissioncables",
		"transmissionlines",
		"generators",
		"load-analysis-counties",
		"substation-grid-locations",
		"nep-ehv",
		"nep-hv"
	])

def prep(scenario=None):

	from .__main__ import main
	main(scenario=scenario, only_prep_gens=True)

def create_model(scenario=None):

	from .__main__ import main
	main(scenario=scenario)
