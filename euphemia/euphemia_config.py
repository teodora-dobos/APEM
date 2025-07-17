from euphemia.enums.cut_types import CutType
from euphemia.enums.datasets import Datasets


class EuphemiaConfig:
    """
    Configuration object for Euphemia algorithm.
    """

    def __init__(self):
        self.scenario = None
        self.set_dataset(Datasets.GENERATED_SMALL)      # "Generated Small" as base dataset

        self.disable_reinsertion = False                # Disable automatic start of reinsertions
        self.price_lower_bound = -500                   # Lower price bound
        self.price_upper_bound = 4000                   # Upper price bound
        self.beta_MIC = 0.1                             # Parameter how much paradoxically accepted MIC must be OTM
        self.delta_load_gradient = 5000                 # Parameter how much paradoxically accepted load gradient must be OTM
        self.epsilon = 1e-4                             # Epsilon for Gurobi float values
        self.max_iterations = 50                        # Iteration Limit
        self.cutting_strategy = CutType.CB              # Cutting strategy to be used
        self.calculate_corrected_welfare = False        # Deduct surplus of inelastic demand from welfare (Only works for 24 periods!)

        self.delta_PAB = 50                             # currently not in use

    def set_dataset(self, dataset):
        """
        Set the dataset to use.
        """
        self.scenario = dataset.value.parse_data()