from apem.EU_market_model.euphemia.enums.cut_types import CutTypes
from apem.EU_market_model.euphemia.enums.datasets import EU_Datasets


class EuphemiaConfig:
    """
    Configuration object for Euphemia algorithm.
    """

    def __init__(self):
        self.scenario = None
        self.set_dataset(EU_Datasets.GENERATED_SMALL)  # "Generated Small" as base dataset
        self.dataset = None

        # Core Euphemia behavior
        self.disable_reinsertion = True  # Disable automatic start of reinsertions
        self.calculate_corrected_welfare = False  # Deduct surplus of inelastic demand from welfare (24 periods only)
        self.cutting_strategy = CutTypes.CB  # Cutting strategy to be used

        # Algorithm parameters
        self.price_lower_bound = -500  # Lower price bound
        self.price_upper_bound = 4000  # Upper price bound
        self.beta_MIC = 0.1  # Parameter how much paradoxically accepted MIC must be OTM
        self.delta_load_gradient = 5000  # Parameter how much paradoxically accepted load gradient must be OTM
        self.delta_PAB = 50  # currently not in use
        self.epsilon = 1e-4  # Epsilon for Gurobi float values
        self.max_iterations = 50  # Iteration Limit
        self.reinsertion_max_iterations = 10  # Iteration limit for reinsertion runs
        self.big_m = 10 ** 6  # Big-M value used in master/pricing formulations

        # Solver parameters
        self.lazy_constraints = 1
        self.output_flag = 0
        self.time_limit = None
        self.mip_gap = None
        self.threads = None
        self.seed = None

    def set_dataset(self, dataset):
        """
        Set the dataset to use.
        """
        self.dataset = dataset.name
        self.scenario = dataset.value.parse_data()

    def apply_overrides(self, overrides):
        """
        Apply validated configuration overrides from config.json.
        """
        if not overrides:
            return

        allowed_keys = {
            "disable_reinsertion",
            "calculate_corrected_welfare",
            "price_lower_bound",
            "price_upper_bound",
            "beta_MIC",
            "delta_load_gradient",
            "delta_PAB",
            "epsilon",
            "max_iterations",
            "reinsertion_max_iterations",
            "big_m",
            "lazy_constraints",
            "output_flag",
            "time_limit",
            "mip_gap",
            "threads",
            "seed",
        }

        unknown = sorted(set(overrides) - allowed_keys)
        if unknown:
            raise ValueError(
                "Invalid Euphemia configuration key(s): "
                + ", ".join(unknown)
            )

        for key, value in overrides.items():
            setattr(self, key, value)
