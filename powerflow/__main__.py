import os, sys, time

# Change working dir to module location

os.chdir(sys.path[0])

commands = sys.argv[1:]

command_tests = {
	'fetch-db': os.path.isfile('data/db_cache/substations.json'),
	'data-prep': os.path.isfile('data/db_cache/generators_aggregate.json'),
	'create-model': os.path.isfile('data/intermediate_model/loads.csv'),
	'analysis': os.path.isfile('results/'),
}

for command in commands:
	if command not in command_tests:
		print(f"Error: Unknown command '{command}'.")
		exit()

target_command = sys.argv[-1]

insert_counter = 0
for command in command_tests:
	if command not in commands and command_tests[command] == False:
		commands.insert(insert_counter, command)
		insert_counter += 1
	if command == target_command:
		break

command_tasks = {
	'fetch-db': ['dataminer', 'fetch_db'],
	'data-prep': ['dataminer', 'prep'],
	'create-model': ['dataminer', 'create_model'],
	'analysis': ['analysis', 'all'],
}

import importlib

for i, command in enumerate(commands):

	print(f"{i+1}/{len(commands)} Starting task '{command}'...")
	start_time = time.time()

	module, function = command_tasks[command]

	i = importlib.import_module('powerflow.'+module)
	getattr(i, function)()

	dm, ds = divmod(time.time() - start_time, 60)
	print(f"Finished task '{command}' after {dm:.0f}:{ds:02.0f}.")
