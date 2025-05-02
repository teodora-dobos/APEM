from apem.execution_chain import solve_and_analyse_scenario
from apem.config_loader import ConfigLoader

def main():
    config = ConfigLoader()
    solve_and_analyse_scenario(
        dataset=config.get_dataset(),
        power_flow_model=config.get_power_flow_model(),
        pricing_algorithm=config.get_pricing_algorithm(),
        redispatch_algorithm=config.get_redispatch_algorithm()
    )

if __name__ == "__main__":
    main()
