from euphemia.enums.datasets import Datasets
from euphemia.enums.cut_types import CutType
from euphemia.euphemia_config import EuphemiaConfig
from euphemia.master_problem.master_problem import MasterProblem



def solve_euphemia(dataset: Datasets, cutting_strategy: CutType):
    config = EuphemiaConfig()
    config.set_dataset(dataset)
    config.cutting_strategy = cutting_strategy
    euphemia = MasterProblem(config)
    euphemia.run()

def run_evaluation(withIEEE: bool = False):
    config = EuphemiaConfig()
    config.disable_reinsertion = True

    datasets = [Datasets.GENERATED_SMALL, Datasets.GENERATED_LARGE, Datasets.GME, Datasets.OMIE, Datasets.ARPA]
    if withIEEE:
        datasets.append(Datasets.IEEE_RTS)
    for dataset in datasets:
        config.set_dataset(dataset)

        print(f"Running Combinatorial Benders Cut on {dataset}")
        config.cutting_strategy = CutType.CB
        euphemia = MasterProblem(config)
        euphemia.run()

        print(f"Running Price-based Cut on {dataset}; beta_MIC=10% delta_load_gradient=10000")
        config.cutting_strategy = CutType.PB
        config.beta_MIC = 0.1
        config.delta_load_gradient = 10000
        euphemia = MasterProblem(config)
        euphemia.run()

        print(f"Running Price-based Cut on {dataset}; beta_MIC=50% delta_load_gradient=70000")
        config.cutting_strategy = CutType.PB
        config.beta_MIC = 0.5
        config.delta_load_gradient = 70000
        euphemia = MasterProblem(config)
        euphemia.run()

        print(f"Running Price-based Cut on {dataset}; beta_MIC=25% delta_load_gradient=40000")
        config.cutting_strategy = CutType.PB
        config.beta_MIC = 0.25
        config.delta_load_gradient = 40000
        euphemia = MasterProblem(config)
        euphemia.run()


    config.cutting_strategy = CutType.NG

    print(f"No good Cut on {Datasets.GENERATED_SMALL}")
    config.set_dataset(Datasets.GENERATED_SMALL)
    config.cutting_strategy = CutType.NG
    euphemia = MasterProblem(config)
    euphemia.run()

    print(f"No good Cut on {Datasets.GME}")
    config.set_dataset(Datasets.GME)
    config.cutting_strategy = CutType.NG
    euphemia = MasterProblem(config)
    euphemia.run()

    print("Evaluation finished")
