import os, json, time
from pathlib import Path

from pymongo import MongoClient, ASCENDING
from bson.json_util import dumps

class DB:

	data_location = os.path.dirname(__file__) + "/../Data/"
	data_cache_location = data_location + "db_cache/"

	def __init__(self):

		with open(Path.home() / 'creds' / 'ma_pfg_mdb_prod', 'r') as credfile:
			db_access_url = credfile.read().rstrip()

		self.client = MongoClient(db_access_url)
		self.db = self.client['test']

	def fetch_data(self, collections):

		print("Fetching from", collections)

		for collection_name in collections:

			print("Fetching", collection_name)
			json_file_name = f"{self.data_cache_location}/{collection_name}.json"

			try:

				collection = self.db[collection_name]

				est_doc_cnt = collection.estimated_document_count()
				print(est_doc_cnt, "documents in collection.")

				if collection_name in ["generators"]:

					with open(json_file_name + 'l', 'wb+') as jsonlfile:

						counter = 0
						last_id = None
						query = {
							"GrossPower": {"$gt": 1}, # 1kW or 20kW
							"UnitOperationalStatus": {
								"$in": ["in operation", "in planning"]
							}
						}
						projection = {
							"_id": 1,
							"UnitMastrNumber": 1,
							"Name": 1,
							"Latitude": 1,
							"Longitude": 1,
							"GrossPower": 1,
							"EnergySource": 1,
							"CommissionDate": 1,
							"ConnectionToMaximumOrHighVoltage": 1,
							"ConnectionToMediumVoltage": 1,
							"UnitOperationalStatus": 1,
							"LocationMaStRNumber": 1
						}

						while True:

							if last_id is not None:
								query["_id"] = {"$gt": last_id}

							cursor = collection.find(query, projection).sort("_id", ASCENDING).limit(1000)

							batch = list(cursor)
							if not batch:
								break

							jsonlines = "\n".join([dumps(item) for item in batch])
							jsonlfile.write(jsonlines.encode('utf-8'))
							jsonlfile.write(b"\n")

							counter += len(batch)
							last_id = batch[-1]["_id"]

							print(f"Wrote {counter:>7}/{est_doc_cnt} gens", end='\r')

							# tiny pause helps with throttling on Atlas
							time.sleep(0.05)

					print("")
					print("Finished writing.")

				else:
					documents = collection.find()

					print("Dumping query results to JSON...")
					json_string = dumps(documents, indent=2)

					print("Writing to local cache...")

					with open(json_file_name, 'w+') as jsonfile:
						jsonfile.write(json_string)
						jsonfile.write('\n')

			except Exception as e:

				print(f"An error occurred fetching data from {collection_name}:", e)
				exit()

if __name__ == "__main__":
	DB().fetch_data(
		[
			"generators",
			"substations",
			"transmissioncables",
			"transmissionlines",
			"load-analysis-counties",
			"substation-grid-locations",
			"nep-ehv",
			"nep-hv"
		]
	)
