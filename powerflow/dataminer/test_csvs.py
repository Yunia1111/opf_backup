import csv

print("Running checks on CSVs...")

bus_list = []

with open('buses.csv') as busfile:

	buses = csv.DictReader(busfile, delimiter=';')
	for row in buses:
		bus_list.append(row['bus_id'])



unfound_buses = set()
loop_conns = set()

with open('connections.csv') as connfile:

	conns = csv.DictReader(connfile, delimiter=';')

	for row in conns:

		startBus = row['from_bus_id']
		endBus = row['to_bus_id']

		if startBus not in bus_list:
			unfound_buses.add(startBus)

		if endBus not in bus_list:
			unfound_buses.add(endBus)

		if startBus == endBus:
			loop_conns.add(f"{startBus}-{endBus}")


print()
print("Dead bus references:", unfound_buses)
print("Total:", len(unfound_buses))

print()
print("Loop conns:", loop_conns)
print("Total:", len(loop_conns))
