"""
Data preprocessor module - cleans and prepares data for network building
"""
import pandas as pd
import numpy as np
from . import config

class DataPreprocessor:
    def __init__(self, data_loader):
        self.buses = data_loader.buses.copy()
        self.connections = data_loader.connections.copy()
        self.generators = data_loader.generators.copy()
        self.loads = data_loader.loads.copy()
        self.transformers = data_loader.transformers.copy()

    def preprocess_all(self):
        """Execute all preprocessing steps"""
        self._calculate_reactive_loads()
        self._scale_loads()
        self._merge_generators()
        self._scale_generation()
        self._process_parallel_lines()
        self._add_transformer_parameters()

        # Print final statistics
        total_gen = self.generators['p_mw'].sum()
        total_load = self.loads['p_mw'].sum()
        print(f"\nPreprocessing complete:")
        print(f"  Generator groups: {len(self.generators)}")
        print(f"  Total Generation: {total_gen:.1f} MW")
        print(f"  Total Load:       {total_load:.1f} MW")
        print(f"  Gen/Load Ratio:   {total_gen/total_load:.3f}")

        return self

    def _calculate_reactive_loads(self):
        """Calculate reactive power Q = P * tan(arccos(pf))"""
        pf = config.POWER_FACTOR
        tan_phi = np.tan(np.arccos(pf))
        self.loads['q_mvar'] = self.loads['p_mw'] * tan_phi

    def _scale_loads(self):
        """Apply overall scaling factor to loads"""
        scale_factor = config.LOAD_SCALING_FACTOR

        if scale_factor != 1.0:
            self.loads['p_mw'] *= scale_factor
            self.loads['q_mvar'] *= scale_factor
            print(f"  Scaled loads by factor: {scale_factor}")

    def _merge_generators(self):
        """Merge generators of same type at same bus"""
        original_count = len(self.generators)

        self.generators = self.generators.groupby(
            ['bus_id', 'generation_type'], as_index=False
        ).agg({
            'p_mw': 'sum',
            'vm_pu': 'mean',
            'sn_mva': 'sum',
            'generator_name': lambda x: f"merged_{x.iloc[0].split('_')[1] if '_' in x.iloc[0] else 'gen'}_{len(x)}units",
            'commissioning_year': 'first'
        })

        print(f"  Merged {original_count} → {len(self.generators)} generator groups")

    def _scale_generation(self):
        """Scale generation by capacity factors and overall scaling factor"""
        capacity_factors = config.GENERATION_CAPACITY_FACTORS

        # Show initial Gen/Load ratio BEFORE capacity factors
        total_gen_initial = self.generators['p_mw'].sum()
        total_load = self.loads['p_mw'].sum()
        ratio_initial = total_gen_initial / total_load if total_load > 0 else 0

        print(f"\n  Initial Gen/Load (before capacity factors): {ratio_initial:.3f}")

        # Step 1: Apply capacity factors by generation type
        print(f"  Applying capacity factors to generation types...")
        for idx, gen in self.generators.iterrows():
            gen_type = str(gen['generation_type']).lower().strip()
            factor = capacity_factors.get(gen_type)

            if factor is None:
                # Try partial match
                for key, cf in capacity_factors.items():
                    if key in gen_type or gen_type in key:
                        factor = cf
                        break

            if factor is not None:
                self.generators.at[idx, 'p_mw'] *= factor
                self.generators.at[idx, 'sn_mva'] *= factor

        total_gen_after_cf = self.generators['p_mw'].sum()
        ratio_after_cf = total_gen_after_cf / total_load if total_load > 0 else 0

        print(f"    After capacity factors: Gen/Load = {ratio_after_cf:.3f}")

        # Step 2: Apply overall generation scaling factor
        overall_factor = config.GENERATION_SCALING_FACTOR

        if overall_factor != 1.0:
            self.generators['p_mw'] *= overall_factor
            self.generators['sn_mva'] *= overall_factor
            print(f"  Applied overall generation scaling: {overall_factor}")

        total_gen_final = self.generators['p_mw'].sum()
        ratio_final = total_gen_final / total_load if total_load > 0 else 0

        print(f"  Final Gen/Load ratio: {ratio_final:.3f}")

    def _process_parallel_lines(self):
        """Process parallel lines and cables per phase"""
        original_count = len(self.connections)

        # Fill missing parallel_cables_per_phase (use .loc to avoid warning)
        self.connections.loc[:, 'parallel_cables_per_phase'] = self.connections['parallel_cables_per_phase'].fillna(1)

        # Adjust impedance for cables per phase
        self.connections['r_ohm_per_km'] = self.connections['r_ohm_per_km'] / self.connections['parallel_cables_per_phase']
        self.connections['x_ohm_per_km'] = self.connections['x_ohm_per_km'] / self.connections['parallel_cables_per_phase']
        self.connections['c_nf_per_km'] = self.connections['c_nf_per_km'] * self.connections['parallel_cables_per_phase']
        self.connections['max_i_ka'] = self.connections['max_i_ka'] * self.connections['parallel_cables_per_phase']

        # Group parallel circuits
        self.connections['parallel'] = 1
        group_cols = ['from_bus_id', 'to_bus_id', 'length_km', 'r_ohm_per_km',
                     'x_ohm_per_km', 'c_nf_per_km', 'max_i_ka', 'line_type', 'ac_dc_type']

        self.connections = self.connections.groupby(group_cols, as_index=False, dropna=False).agg({
            'parallel': 'sum',
            'name': 'first',
            'geographic_coordinates': 'first',
            'parallel_cables_per_phase': 'first',
            'switch_group': 'first',
            'commissioning_year': 'first'
        })

        print(f"  Processed parallel lines: {original_count} → {len(self.connections)}")

    def _add_transformer_parameters(self):
        """Add missing necessary standard transformer parameters"""
        self.transformers['vk_percent'] = config.TRAFO_VK_PERCENT
        self.transformers['vkr_percent'] = config.TRAFO_VKR_PERCENT
        self.transformers['pfe_kw'] = config.TRAFO_PFE_KW
        self.transformers['i0_percent'] = config.TRAFO_I0_PERCENT
