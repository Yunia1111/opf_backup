def fetch_db():

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

def prep():

	from .__main__ import main
	main(only_prep_gens=True)

def create_model():

	from .__main__ import main
	main()
