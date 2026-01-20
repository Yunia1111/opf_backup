import sys, os

from .model import *
from .map import create_map
from .db import DB

MAX_DISTANCE_SAME_SUBSTATION_M = 50
MAX_DISTANCE_SAME_CONN_POINT_M = 20
MAX_DISTANCE_BRANCH_M = 10
MAX_DISTANCE_SUBSTATION_M = 500

DEFAULT_SCENARIO = {
	'min_voltage': 200000,
	'year': 2035,
	'location': None # {'lat': 0, 'lon': 0, 'r_km': 50}
}

# TODO: CLI to adjust scenario

# TODO: Look for disconnected buses using the analysis result maps
# TODO: Also use collection `loads`

# Next: 110kV:
# - define 50km Radius in scenario
# - Add all 110kV lines
# - Define all 110kV+EHV substations as slack buses for the external transfer


if len(sys.argv) >= 2 and sys.argv[1] == "--fetch-new-data":
	db = DB()
	db.fetch_data(
		[
			"substations",
			"transmissioncables",
			"transmissionlines",
			"generators",
			"load-analysis-counties",
			"substation-grid-locations",
			"nep-ehv",
			"nep-hv"
		] if (len(sys.argv) >= 3 and sys.argv[2] == "all") else [
			"substations",
			"transmissioncables",
			"transmissionlines",
		]
	)
	exit()

dataloc = DB.data_location
datadir = DB.data_cache_location
csv_dir = 'data/intermediate_model/'

if not os.path.exists(csv_dir):
	os.makedirs(csv_dir)



def main(scenario=DEFAULT_SCENARIO, only_prep_gens=False):

	# TODO: add location filter (coords+radius)
	def scenarioFilter(item):

		if item.max_v() < scenario['min_voltage']:
			return False

		if item.comm_year != None and item.comm_year > scenario['year']:
			return False

		return True

	TransmissionLine.load_from_json(
		datadir + "transmissionlines.json",
		filter_f=scenarioFilter
	)

	TransmissionCable.load_from_json(
		datadir + "transmissioncables.json",
		filter_f=scenarioFilter
	)

	Substation.load_from_json(
		datadir + "substations.json",
		filter_f=scenarioFilter
	)

	print("\n\n   >>>   Base Import Complete   <<<   \n\n")

	### NEP
	# TODO: Move to its own file/module

	include_nep = True
	if include_nep:

		# nep-ehv and nep-hv
		# TODO: nep-hv
		# Netzentwicklungsplan
		# New lines and substations
		# Convert into realistic line

		Substation.build_search_tree()
		Connection.build_search_tree()

		with open(datadir + "nep-ehv.json") as f:
			raw_nep_items = json.load(f)

		added_cap_num = defaultdict(int)
		added_cap_sum_mva = defaultdict(int)
		added_cap_sum_rel = defaultdict(int)

		sub_not_found = 0

		conn_counter = 0
		found_conn_counter = 0

		max_comm_year = 0

		# === PASS 1 ===
		# Calculated the average relative capacity increase
		# To be used for the many entries that don't have an "Added Capacity" field
		print("Scanning NEP entries...")
		for ni, nep_item in enumerate(raw_nep_items):

			print(f"NEP {ni:>5}/{len(raw_nep_items)}", end='\r')

			cy = nep_item["properties"].get('Commissioning Date')
			if cy and cy != "N/A" and int(cy) > max_comm_year:
				max_comm_year = int(cy)

			mva_base = 0

			# try to find existing item
			nep_element = nep_item["properties"]["Element"].lower()
			nep_elements = nep_element.split(', ')
			if "substation" in nep_elements:

				coords = Coords(reversed(nep_item["geometry"]["coordinates"]))
				close_subs = Substation.search(coords, MAX_DISTANCE_SAME_SUBSTATION_M)
				if len(close_subs) >= 1:
					total_power = sum([Node.get(sub).power for sub in close_subs])
					mva_base = (total_power / len(close_subs)) / 1e6
					# Note down for later
					nep_item['_existing_subs'] = close_subs
				else:
					sub_not_found += 1

			if "line" in nep_elements or "cable" in nep_elements:

				conn_counter += 1

				found_adj = {}
				found_conns = set()

				for corner in nep_item["geometry"]["coordinates"]:
					coords = Coords(reversed(corner))
					neighbors = Connection.search(coords, MAX_DISTANCE_SAME_CONN_POINT_M)
					if neighbors:

						for cid, endtype in neighbors.items():
							if (cid in found_adj) and (found_adj[cid] != endtype):
								found_conns.add(cid)

						found_adj |= neighbors

				if len(found_conns) >= 1:
					found_conn_counter += 1

					# Save found_conns for later
					nep_item['_existing_conns'] = found_conns

					if not nep_item["properties"].get("Added Capacity"):

						num_systems = 0
						for cid in list(found_conns):
							conn = Connection.get(cid)
							for c in conn.circuits:
								mva_base += c.capacity or c.fallback_capacity()
								num_systems += c.systems
						mva_base /= len(found_conns)
						num_systems = round(num_systems/len(found_conns))

						mva_new = num_systems * 380 * 2 # everything in EHV is being upgraded to 380kV 2kA basically. Stefan said this is fine.
						mva_inc = mva_new - mva_base

						# TODO: Find a better way to prevent this
						if mva_inc < 0:
							print('Negative increase, very unlikely!')
							continue

						for el in nep_elements:
							added_cap_num[el] += 1
							added_cap_sum_mva[el] += mva_inc
							added_cap_sum_rel[el] += mva_inc/mva_base

			# calc added cap
			added_cap = nep_item["properties"].get("Added Capacity")
			if added_cap and mva_base > 0:
				if added_cap[-4:] == " MVA":
					mva_inc = int(added_cap[:-4])
					for el in nep_elements:
						added_cap_num[el] += 1
						added_cap_sum_mva[el] += mva_inc
						added_cap_sum_rel[el] += mva_inc/mva_base

					nep_item['_cap_inc_mva'] = mva_inc
					nep_item['_cap_inc_rel'] = mva_inc/mva_base
				else:
					print('')
					print('Offending NEP entry:')
					print(nep_item)
					raise Exception("Not '\\d MVA'")

		average_added_cap_mva = {el: cap_sum_mva/added_cap_num[el] for el, cap_sum_mva in added_cap_sum_mva.items()}
		average_added_cap_rel = {el: cap_sum_rel/added_cap_num[el] for el, cap_sum_rel in added_cap_sum_rel.items()}

		print('')
		print("NEP first pass done:")
		print('MVA:', average_added_cap_mva)
		print('rel:', average_added_cap_rel)
		print(sub_not_found, "Substations could not be correlated.")
		print(f"{found_conn_counter}/{conn_counter} connections could be correlated.")

		# === PASS 2 ===
		# Add the data to the model (new power, voltages, etc. with comm_year flag)
		print("Adding NEP entries...")

		for ni, nep_item in enumerate(raw_nep_items):

			print(f"NEP {ni:>5}/{len(raw_nep_items)}", end='\r')

			nep_element = nep_item["properties"]["Element"].lower()
			nep_elements = nep_element.split(', ')

			# Skip if later than scenario year
			try:
				comm_year = int(nep_item["properties"]['Commissioning Date'])
				if comm_year > scenario['year']:
					print("\nNot commissioned yet:", comm_year)
					continue
			except ValueError:
				#print("\nNo commissioning year:", nep_item["properties"]['Commissioning Date'], "using fallback:", max_comm_year)
				comm_year = max_comm_year

			# Otherwise, apply power increase
			if "substation" in nep_elements:

				if '_existing_subs' in nep_item:
					for sub_id in nep_item['_existing_subs']:
						sub = Node.get(sub_id)
						if '_cap_inc_mva' in nep_item:
							sub.power += nep_item['_cap_inc_mva']
						else:
							sub.power *= average_added_cap_rel["substation"]
				else:
					added_cap = nep_item["properties"].get("Added Capacity")
					if added_cap and added_cap[-4:] == " MVA":
						power_mva = int(added_cap[:-4])
					else:
						power_mva = average_added_cap_mva["substation"]

					sub_props = {
						'Id': nep_item['_id']['$oid'], # Unfortunately no more stable ID available
						'Latitude': nep_item["geometry"]["coordinates"][1],
						'Longitude': nep_item["geometry"]["coordinates"][0],
						'Name': nep_item["properties"]["Name"],
						'Operator': nep_item["properties"]["Operator"],
						'_Power': power_mva,
						'_Comm_Year': comm_year,
					}
					for key, voltage in nep_item["properties"].items():
						if key.startswith('Voltage_'):
							sub_props[f"KV{int(voltage)//1000}"] = True

					try:
						Substation(sub_props, filter_f=scenarioFilter)
					except FilteredItem as e:
						continue

			if "line" in nep_elements or "cable" in nep_elements:

				# NOTE: We diregard the "upgraded line" situation
				# because it's incredibly hard to correlate them
				# Therefore, a new line for each NEP entry. Should be fine.

				added_cap = nep_item["properties"].get("Added Capacity")
				if added_cap and added_cap[-4:] == " MVA":
					power_mva = int(added_cap[:-4])
				else:
					power_mva = average_added_cap_mva["substation"]

				voltages = [int(voltage) for key, voltage in nep_item["properties"].items() if key.startswith('Voltage_') and voltage and voltage != "N/A"]
				if len(voltages) < 1:
					voltages = [380000]

				# QUESTION: Split power increase proportionately into voltages instead of equally?
				capacities = {voltage: (power_mva/len(voltages)) for voltage in voltages} # MVA

				frequency = nep_item["properties"]["Frequency"]
				circuits = len(voltages) # or more depending on capacity?
				cables = circuits * (3 if frequency == '50' else 2)

				try:
					Connection(
						nep_item['_id']['$oid'], # Unfortunately no more stable ID available
						ConnType.LINE if "line" in nep_elements else ConnType.CABLE,
						voltages,
						capacities,
						{},
						{},
						frequency,
						str(circuits),
						str(cables),
						nep_item["properties"]["Operator"],
						nep_item["geometry"]["coordinates"],
						comm_year=comm_year,
						filter_f=scenarioFilter
					)
				except FilteredItem as e:
					continue


		print("NEP second pass done.")


	print("Completed import.")
	print("Conn Entries:", len(Connection._all))
	print("Node Entries:", len(Node._all))

	# TODO: Fuse close substations
	# <100m <52.537662,13.537328>
	# but sometimes up to 400m <52.53992,13.706795>

	### Connect lines and cables geographically using branches ###

	Substation.build_search_tree()

	Connection.build_search_tree()

	print("Going through all connection points and connecting them to Subs or Branches...")

	for ci, connpoint in enumerate(Connection.connpoint_list):

		print(f"{ci:>5}/{len(Connection.connpoint_list)}", end='\r')

		# Search for other nearby (10m) line ends to connect
		conn_pool = Connection.search(connpoint, MAX_DISTANCE_BRANCH_M)
		# conn_pool signature = {'<conn_id>': '<end_type>', ...}

		# QUESTION: Apparently these are sometimes up to 80m away
		# See e.g. <52.495203,13.33442>, that's probs connected, amirite?

		node = None

		# Seach substations within 500m
		subs = Substation.search(connpoint, MAX_DISTANCE_SUBSTATION_M)

		if len(subs) >= 1:
			# Substations -> Use closest substation as connection for line ends

			# Sort by increasing distance
			subs.sort(key=lambda sub_id: connpoint.distance_to(Node.get(sub_id).coords))

			# Choose closest for connecting line ends
			node = Node.get(subs[0])
			node.add_conns(conn_pool)
			# NOTE: look at 67b04fd825fabcec747e15e2:
			# Due to overlap with another conn end it's sometimes closer to one sub
			# and sometimes closer to another. Hence, it's added to both as a conn
			# Nut doesn't necessarily have both of them as end points.
			# This is trouble later when deleting.

			# QUESTION: Allow multiple subs to be connected to one line point?
			# See substation way/39243044 and way/1080486178

		else:
			# No Substation -> Just connect line ends using branch
			try:
				node = Branch(Coords(connpoint), conn_pool)
			except AlreadyExistsException as e:
				continue

		for conn_id in conn_pool:
			end_type = conn_pool[conn_id]
			c = Connection.get(conn_id)
			if end_type == EndType.START:
				if c.endNode != node.id: # Prevent self loops
					c.startNode = node.id
			elif end_type == EndType.END:
				if c.startNode != node.id: # Prevent self loops
					c.endNode = node.id

	# TODO: Go through substations that aren't connected (at all or to the overall grid) yet
	# and try to find nearby lines that don't have ends nearby, only line segments


	# The DB values don't always match the connected lines,
	# so we override self.voltages with the connected ones
	Node.update_all_voltages_from_conns()


	print("")
	print("Node entries before island removal:", len(Node._all))
	print("Conn entries before island removal:", len(Connection._all))

	#create_map(
	#	Node._all.values(),
	#	Connection._all.values(),
	#	[], #Generator._all.values(),
	#	"maps/debug_map_with_islands.html"
	#)

	# Remove Islands
	# This process produces Islands, but PandaPower can only handle one network

	start_node = "46615737" # Charlottenburg

	unvisited_nodes = set(Node._all.keys())
	unvisited_conns = set(Connection._all.keys())

	current_node_stack = [start_node]

	print("Starting DFS island filter run...")

	# 68972b50a23e727d8888d7d8_220 -> No 380kV on Sub?

	while(1):

		current_node = current_node_stack[-1]
		unvisited_nodes.discard(current_node)

		new_unvisited_node = None

		for cid in Node.get(current_node).connections:

			if cid not in unvisited_conns:
				continue

			unvisited_conns.discard(cid)
			c = Connection.get(cid)

			other_side = c.endNode if c.startNode == current_node else c.startNode
			if other_side in unvisited_nodes:
				new_unvisited_node = other_side
				break

		if (new_unvisited_node):
			current_node_stack.append(new_unvisited_node)
		else:
			current_node_stack.pop()
			if len(current_node_stack) == 0:
				break

	print("Island detection run finished")
	print("Islands to be deleted:")
	print("Nodes:", len(unvisited_nodes))
	print("Conns:", len(unvisited_conns))

	print("Deleting...")
	for i, nid in enumerate(unvisited_nodes):
		print(f"Node {i:>5}/{len(unvisited_nodes)}", end='\r')
		Node.get(nid).delete()

	print("")
	for i, cid in enumerate(unvisited_conns):
		print(f"Conn {i:>5}/{len(unvisited_conns)}", end='\r')
		Connection.get(cid).delete()

	print("")
	print("Deleted", len(Substation._deleted_subs), " Substations")

	with open("deleted_subs.txt", "w+") as f:
		f.write("\n".join(Substation._deleted_subs))
		f.write("\n")

	with open("deleted_conns.txt", "w+") as f:
		f.write("\n".join(Connection._deleted_conns))
		f.write("\n")

	print("Node entries after island removal:", len(Node._all))
	print("Conn entries after island removal:", len(Connection._all))

	Node.write_csv(csv_dir + "buses.csv")
	Connection.write_csv(
		csv_dir + "connections.csv",
		csv_dir + "connections_wiredata.csv", Node.get
	)
	Transformer.write_csv(csv_dir + "transformers.csv")

	unfound_buses = Connection.test_refs(Node._all.keys())
	print("NIDs in conns but not in nodes:")
	print(unfound_buses)
	if unfound_buses not in [set(), set([None])]:
		raise Exception("Null references in conns!")
		exit()



	### Load and attach generators ###

	# Rebuild search tree because some nodes were deleted
	Substation.build_search_tree()

	if (only_prep_gens):
		print("Pre-processing generators (this may take a while, it's over 6M)")

		Generator.pre_process_json_cache(
			datadir + "generators.jsonl",
			datadir + "generators_aggregate.json",
			datadir + "substation-grid-locations.json",
			oceans_file = (dataloc + "Ocean_Data/ne_10m_ocean.shp")
		)

		return

	Generator.load_from_json(
		datadir + "generators_aggregate.json",
		scenario=scenario
	)

	# NOTE: Closest sub is not always the correct one, but mostly

	print("Generator Entries:", len(Generator._all))

	Generator.write_csv(csv_dir + "generators.csv")

	create_map(
		Node._all.values(),
		Connection._all.values(),
		[], #Generator._all.values(),
		"maps/debug_map.html"
	)



	print("Loading region data...")

	Load.load_from_json(
		datadir + "load-analysis-counties.json",
		scenario=scenario
	)


	import geopandas as gpd
	import shapely

	regions_gdf = gpd.read_file(dataloc + "kreise.json", engine="pyogrio")
	reg_polygons = regions_gdf.geometry.tolist()

	reg_tree = shapely.STRtree(reg_polygons)

	sub_ids, sub_points = zip(*[
		(nid, shapely.Point(n.coords.lon, n.coords.lat))
		for nid in Node._all if (n := Node.get(nid)).type == NodeType.SUBSTATION
	])

	print("Regions:", len(reg_polygons))
	print("Subs:", len(sub_points))

	print("Associationg substations with regions...")

	sub_indices, region_indices = reg_tree.query(sub_points, predicate="intersects")

	print("Assigning substations to regions and vv...")

	for sub_i, reg_i in zip(sub_indices, region_indices):

		sub_id = sub_ids[sub_i]
		nuts_id = regions_gdf.NUTS[reg_i]

		Node.get(sub_id).region = nuts_id
		Load.get(nuts_id).add_substation(sub_id)


	print("Going through regions and writing loads...")

	Load.write_csv(csv_dir + 'loads.csv')

	print("Total load (for sanity check):", round(Load.total_load()/1000, 3), "GW (should be ~52GW)")
	print("Assigned load (for sanity check):", round(Load.agg/1000, 3), "GW (should be ~50GW)")

	print(f"Done.")

if __name__ == "__main__":
    main()
