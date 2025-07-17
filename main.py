from apem.execution_chain import solve_and_analyse_scenario
from apem.config_loader import ConfigLoader

from euphemia.enums.cut_types import CutType
from euphemia.execution_chain import Datasets as EuphemiaDatasets, run_evaluation, run_IEEE_evaluation
from euphemia.execution_chain import solve_euphemia as solve_euphemia


def main():
    # Euphemia example
    # solve_euphemia(EuphemiaDatasets.IEEE_RTS, CutType.PB)
    # run_evaluation(withIEEE=True)
    # run_IEEE_evaluation()

    config = ConfigLoader()
    solve_and_analyse_scenario(
        dataset=config.get_dataset(),
        power_flow_model=config.get_power_flow_model(),
        pricing_algorithm=config.get_pricing_algorithm(),
        redispatch_algorithm=config.get_redispatch_algorithm()
    )


if __name__ == "__main__":
    main()
