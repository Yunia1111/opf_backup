"""
Data loader module - reads all CSV files
"""
import pandas as pd
import os
from . import config

class DataLoader:
    def __init__(self):
        self.buses = None
        self.connections = None
        self.generators = None
        self.loads = None
        self.transformers = None
        self.external_grids = None

    def load_all(self):
        """Load all required data files"""
        self.buses = self._load_csv(config.BUSES_FILE)
        self.connections = self._load_csv(config.CONNECTIONS_FILE)
        self.generators = self._load_csv(config.GENERATORS_FILE)
        self.loads = self._load_csv(config.LOADS_FILE)
        self.transformers = self._load_csv(config.TRANSFORMERS_FILE)

        # Load external grids file (mandatory - must have at least one slack bus)
        ext_grid_path = os.path.join(config.DATA_DIR, config.EXTERNAL_GRIDS_FILE)
        if not os.path.exists(ext_grid_path):
            raise FileNotFoundError(
                f"External grids file not found: {ext_grid_path}\n"
                "This file is mandatory and must define at least one slack bus."
            )

        self.external_grids = pd.read_csv(ext_grid_path, sep=';')

        if len(self.external_grids) == 0:
            raise ValueError(
                "external_grids.csv is empty. "
                "At least one slack bus must be defined."
            )

        print(f"Loaded {len(self.external_grids)} external grids (slack buses)")

        print(f"Loaded: {len(self.buses)} buses, {len(self.connections)} connections, "
              f"{len(self.generators)} generators, {len(self.loads)} loads, "
              f"{len(self.transformers)} transformers")
        return self

    def _load_csv(self, filename):
        """Load a single CSV file"""
        filepath = os.path.join(config.DATA_DIR, filename)
        return pd.read_csv(filepath, sep=';')
