Blindleister Power Flow
=======================

This repository contains:

## The powerflow script

- CLI and option system for running power flow analyses
- Execute dataminer and flow analysis modules

## Data Miner

- Fetch data from Blindleister DB
- Process and clean up data
- Assemble features into grid model
- Export Model into intermediate CSVs for analysis

## Analysis

- Load Model from CSVs into PandaPower
- Run power flow
- Provide results graphically

# Install and run

## Setup

```sh
python -m venv .				# Create Virtual Env
. bin/activate					# Activate VEnv
pip install -r requirements.txt	# Install requirements
```

## First Run

```sh
python -m powerflow <sequence of tasks>
```

where tasks can be `fetch-db`, `data-prep`, `create-model`, `analysis`.

For example:

```sh
python -m powerflow fetch-db data-prep create-model
```

If previous steps have never been executed and therefore their data is missing,
they are executed beforehand automatically.

They only need to be stated explicitly if you want them to be re-run, e.g. to
update their data.

So normally, you can just run the target step you're working on:


```sh
python -m powerflow analysis
```

and everything should work using the existing data from previous steps.
