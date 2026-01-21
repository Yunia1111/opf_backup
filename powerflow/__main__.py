import os, sys, time
import argparse, json
from datetime import datetime

# Change working dir to module location

os.chdir(sys.path[0])

# Everything about each command
command_info = {
	'fetch-db': {
		'test': os.path.isfile('data/db_cache/substations.json'),
		'module': 'dataminer',
		'function': 'fetch_db'
	},
	'data-prep': {
		'test': os.path.isfile('data/db_cache/generators_aggregate.json'),
		'module': 'dataminer',
		'function': 'prep'
	},
	'create-model': {
		'test': os.path.isfile('data/intermediate_model/loads.csv'),
		'module': 'dataminer',
		'function': 'create_model'
	},
	'analysis': {
		'test': os.path.isfile('results/'),
		'module': 'analysis',
		'function': 'all'
	},
}


# Set up CLI arguments
parser = argparse.ArgumentParser(
	prog='powerflow',
	description='Grid model and power flow simulation and analysis tool',
	epilog='See https://github.com/blindleister/power-flow for more info.'
)

parser.add_argument(
	'commands',
	metavar='command',
	choices=command_info.keys(),
	nargs='+',
	help=f"""
		A sequence of commands to be run. Available commands are:
		{{\x1b[1;31m{', '.join(command_info.keys())}\x1b[0m}}.
		Each preceding command that has not been run will be run automatically.
	"""
)

parser.add_argument('--year', type=int, default=datetime.today().year,
	help="Use grid model for this year (format YYYY)")

parser.add_argument('--area', type=float, nargs=2,
	help="Only model & sim area centered here (requires --radius) (format LATITUDE LONGITUDE as floats)")

parser.add_argument('--radius', type=float,
	help="Radius for area filter (requires --are) (in km, default 50km)")

parser.add_argument('--min-voltage', type=int, default=0,
	help="Only model grid parts with at least this voltage (in kV)")

parser.add_argument('--max-voltage', type=int, default=float("inf"),
	help="Only model grid parts with at most this voltage (in kV)")

args = parser.parse_args()

if args.radius and not args.area:
    parser.error("--radius can only be used with --area")

if args.area and not (40.0 < args.area[0] <= 60.0):
    parser.error("Area center LATITUDE seems to be outside of germany")

if args.area and not (0.0 < args.area[1] <= 20.0):
    parser.error("Area center LONGITUDE seems to be outside of germany")

if args.area and not (0.1 < args.radius <= 500.0):
    parser.error("Area radius must be between 0.1 and 500km")


# Build scenario dict
scenario = {
	'year': args.year,
	'area': {
		'lat': args.area[0],
		'lon': args.area[1],
		'r_km': args.radius or 50
	} if args.area else None,
	'min_voltage': args.min_voltage * 1000,
	'max_voltage': args.max_voltage * 1000
}

print("")
print("   >>> THE FOLLOWING SCENARIO WILL BE USED: <<<")
print("")
print(json.dumps(scenario, indent=4))
print("")



commands = args.commands

# Fill command list with all non-run commands up to the target
target_command = commands[-1]

insert_counter = 0
for command in command_info:
	if command not in commands and command_info[command]['test'] == False:
		commands.insert(insert_counter, command)
		insert_counter += 1
	if command == target_command:
		break

CMD_COLOR = '\x1b[0;32m'
RST_COLOR = '\x1b[0m'

print("Command sequence to be executed:")
for i, c in enumerate(commands):
	print(f"{i+1}. '{CMD_COLOR}{c}{RST_COLOR}'")
print("")

for i in range(3,0,-1):
	print(f"You have {i} seconds to abort (ctrl+c)...", end="\r", flush=True)
	time.sleep(1)
print("You have 0 seconds to abort (ctrl+c)...\n")

# Import and run the function for each command
import importlib

for i, command in enumerate(commands):

	print("")
	print(f" > {i+1}/{len(commands)} Starting task '{CMD_COLOR}{command}{RST_COLOR}'...")
	print("")

	module = command_info[command]['module']
	i = importlib.import_module('powerflow.'+module)

	function = command_info[command]['function']

	start_time = time.time()

	# Run
	getattr(i, function)(scenario=scenario)

	dm, ds = divmod(time.time() - start_time, 60)

	print("")
	print(f" > Finished task '{CMD_COLOR}{command}{RST_COLOR}' after {dm:.0f}:{ds:02.0f}.")
	print("")
