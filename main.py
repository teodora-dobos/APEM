from apem.execution_chain import solve_and_analyse_scenario

from apem.config_loader import ConfigLoader


def main():
    config = ConfigLoader()
    solve_and_analyse_scenario(
        US_dataset=config.get_US_dataset(),
        EU_dataset=config.get_EU_dataset(),
        market_model=config.get_market_model(),
        power_flow_model=config.get_power_flow_model(),
        cut_type=config.get_cut_type(),
        pricing_algorithm=config.get_pricing_algorithm(),
        redispatch_algorithm=config.get_redispatch_algorithm()
    )


if __name__ == "__main__":
    main()
