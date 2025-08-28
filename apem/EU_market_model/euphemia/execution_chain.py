from apem.EU_market_model.euphemia.enums.datasets import EU_Datasets
from apem.EU_market_model.euphemia.enums.cut_types import CutTypes
from apem.EU_market_model.euphemia.euphemia_config import EuphemiaConfig
from apem.EU_market_model.euphemia.master_problem.master_problem import MasterProblem


def solve_euphemia(dataset: EU_Datasets, cut_type: CutTypes):
    """
    Solves an Euphemia scenario.
    Args:
        dataset (Datasets): Used dataset.
        cut_type (CutTypes): Cutting strategy to be used in the solver.

    Returns:

    """
    config = EuphemiaConfig()
    config.set_dataset(dataset)
    config.cutting_strategy = cut_type
    euphemia = MasterProblem(config)
    euphemia.run()


def run_evaluation():
    config = EuphemiaConfig()
    config.disable_reinsertion = True

    datasets = [EU_Datasets.GENERATED_SMALL, EU_Datasets.GENERATED_LARGE, EU_Datasets.GME, EU_Datasets.OMIE,
                EU_Datasets.ARPA]

    for dataset in datasets:
        config.set_dataset(dataset)

        print(f"Running Combinatorial Benders Cut on {dataset}")
        config.cutting_strategy = CutTypes.CB
        euphemia = MasterProblem(config)
        euphemia.run()

        print(f"Running Price-based Cut on {dataset}; beta_MIC=10% delta_load_gradient=10000")
        config.cutting_strategy = CutTypes.PB
        config.beta_MIC = 0.1
        config.delta_load_gradient = 10000
        euphemia = MasterProblem(config)
        euphemia.run()

        print(f"Running Price-based Cut on {dataset}; beta_MIC=50% delta_load_gradient=70000")
        config.cutting_strategy = CutTypes.PB
        config.beta_MIC = 0.5
        config.delta_load_gradient = 70000
        euphemia = MasterProblem(config)
        euphemia.run()

        print(f"Running Price-based Cut on {dataset}; beta_MIC=25% delta_load_gradient=40000")
        config.cutting_strategy = CutTypes.PB
        config.beta_MIC = 0.25
        config.delta_load_gradient = 40000
        euphemia = MasterProblem(config)
        euphemia.run()

    config.cutting_strategy = CutTypes.NG

    print(f"No good Cut on {EU_Datasets.GENERATED_SMALL}")
    config.set_dataset(EU_Datasets.GENERATED_SMALL)
    config.cutting_strategy = CutTypes.NG
    euphemia = MasterProblem(config)
    euphemia.run()

    print(f"No good Cut on {EU_Datasets.GME}")
    config.set_dataset(EU_Datasets.GME)
    config.cutting_strategy = CutTypes.NG
    euphemia = MasterProblem(config)
    euphemia.run()

    print("Evaluation finished")


def run_IEEE_evaluation():
    config = EuphemiaConfig()
    config.disable_reinsertion = True
    config.calculate_corrected_welfare = True
    config.set_dataset(EU_Datasets.IEEE_RTS)

    print(f"Running Combinatorial Benders Cut on {EU_Datasets.IEEE_RTS}")
    config.cutting_strategy = CutTypes.CB
    euphemia = MasterProblem(config)
    euphemia.run()

    print(f"Running Price-based Cut on {EU_Datasets.IEEE_RTS}; beta_MIC=10% delta_load_gradient=10000")
    config.cutting_strategy = CutTypes.PB
    config.beta_MIC = 0.1
    config.delta_load_gradient = 10000
    euphemia = MasterProblem(config)
    euphemia.run()

    print(f"Running Price-based Cut on {EU_Datasets.IEEE_RTS}; beta_MIC=50% delta_load_gradient=70000")
    config.beta_MIC = 0.5
    config.delta_load_gradient = 70000
    euphemia = MasterProblem(config)
    euphemia.run()

    print(f"Running Price-based Cut on {EU_Datasets.IEEE_RTS}; beta_MIC=25% delta_load_gradient=40000")
    config.beta_MIC = 0.25
    config.delta_load_gradient = 40000
    euphemia = MasterProblem(config)
    euphemia.run()
