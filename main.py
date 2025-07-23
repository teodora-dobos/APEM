from apem.execution_chain import solve_and_analyse_scenario
from apem.config_loader import ConfigLoader

from apem.data.parsing.parse_ieee_rts import ParseIEEERTS
from euphemia.enums.cut_types import CutType
from euphemia.execution_chain import Datasets as EuphemiaDatasets, run_evaluation, run_IEEE_evaluation
from euphemia.execution_chain import solve_euphemia as solve_euphemia
from euphemia.data.conversion.run_us_eu_conversion import run_us_eu_conversion


def main():
    euphemia = True

    # Euphemia example
    if euphemia:
        solve_euphemia(EuphemiaDatasets.GME, CutType.PB)
        # run_evaluation()
        # run_IEEE_evaluation()
        # run_us_eu_conversion(ParseIEEERTS,
        #                      generate_uptime_patterns=True,
        #                      use_contiguous_patterns=True,
        #                      reduce_linked_blocks=True,
        #                      compress_identical_blocks=True)

    else:
        config = ConfigLoader()
        solve_and_analyse_scenario(
            dataset=config.get_dataset(),
            power_flow_model=config.get_power_flow_model(),
            pricing_algorithm=config.get_pricing_algorithm(),
            redispatch_algorithm=config.get_redispatch_algorithm()
        )


if __name__ == "__main__":
    main()
