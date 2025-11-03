import sys, os

from .model import *
from .map import create_map
from .db import DB

MAX_DISTANCE_SAME_SUBSTATION_M = 50
MAX_DISTANCE_BRANCH_M = 10
MAX_DISTANCE_SUBSTATION_M = 500

# TODO: Should support exporting filtered variants of data
# e.G. "Only this circular area" or "Only over 200kV"

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



def main(only_prep_gens=False):

	def voltageFilter(item):

		# Ignore under 200kV for now
		if item.max_v() < 200000:
			return False

		return True

	TransmissionLine.load_from_json(
		datadir + "transmissionlines.json",
		filter_f=voltageFilter
	)

	TransmissionCable.load_from_json(
		datadir + "transmissioncables.json",
		filter_f=voltageFilter
	)

	Substation.load_from_json(
		datadir + "substations.json",
		filter_f=voltageFilter
	)

	### NEP

	include_nep = False
	if include_nep:

		# TODO: nep-ehv and nep-hv
		# Netzentwicklungsplan
		# New lines and substations
		# Convert into realistic line
		# Use average for non-given values

		Substation.build_search_tree()

		with open(datadir + "nep-hv.json") as f:
			raw_nep_items = json.load(f)

		added_cap_sum = 0
		added_cap_sum_rel = 0

		# TODO: Do two passes:
		# - one for calculating the average relative capacity increase
		# - and then one to actually add the data (new power, voltages, etc. with comm_year flag)
		for nep_item in raw_nep_items:

			# try to find existing item
			nep_element = nep_item["properties"]["Element"]
			if "Substation" in nep_element:
				coords = Coords(reversed(nep_item["geometry"]["coordinates"]))
				closest_sub = Node.get(Substation.search_closest(coords))
				distance = closest_sub.coords.distance_to(coords)
				if (distance < MAX_DISTANCE_SAME_SUBSTATION_M):
					mva_base = closest_sub.power / 1e6

			elif "Line" in nep_element or "Cable" in nep_element:
				# 1. Find existing from just start+end or all geom points?
				# Latter is probs difficult, needs some similarity heuristic
				pass

			# calc added cap
			added_cap = nep_item["properties"].get("Added Capacity")
			if added_cap:
				if added_cap[:-4] == " MVA":
					mva_inc = int(added_cap[:-4])
					added_cap_sum += mva_inc
					added_cap_sum_rel += mva_inc/mva_base
				else:
					raise Exception("Not '\d MVA'")

			comm_year = nep_item["properties"]["Commissioning Date"]

			# TODO: Also Process: Voltages, Frequency?




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
	#	"Maps/debug_map_with_islands.html"
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
		datadir + "generators_aggregate.json"
	)

	# NOTE: Closest sub is not always the correct one, but mostly

	print("Generator Entries:", len(Generator._all))

	Generator.write_csv(csv_dir + "generators.csv")

	#create_map(
	#	Node._all.values(),
	#	Connection._all.values(),
	#	[], #Generator._all.values(),
	#	"maps/debug_map.html"
	#)



	print("Loading region data...")

	Load.load_from_json(
		datadir + "load-analysis-counties.json",
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
