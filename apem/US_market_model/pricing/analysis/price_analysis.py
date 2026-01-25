from typing import Optional, Tuple

import os
import pandas as pd

from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC import Zonal_NTC
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_fbmc_included import ZonalFBMC
from apem.US_market_model.allocation.allocation import Allocation
from apem.US_market_model.allocation.configuration import Configuration
from apem.US_market_model.data.analysis.plot import plot_supply_demand
from apem.US_market_model.data.parsing.scenario import Scenario
from apem.US_market_model.pricing.algorithms.elmp import ELMP
from apem.US_market_model.pricing.algorithms.ip import IP
from apem.US_market_model.pricing.algorithms.min_mwp import MinMWP
from apem.US_market_model.pricing.analysis.plot import plot_avg_prices, plot_price_heatmap
from apem.US_market_model.pricing.analysis.pricing import GLOCS, LLOCS, MWPS, Pricing


class PriceAnalysis:
    def __init__(
        self,
        scenario: Scenario,
        allocation: Allocation,
        pricing: Pricing,
        configuration: Configuration,
        base_scenario: Optional[Scenario] = None,
    ):
        self.scenario = scenario
        self.allocation = allocation
        self.pricing = pricing
        self.configuration = configuration
        self.base_scenario = base_scenario  # used only for zonal_NTC

    def compute_glocs(self, file_glocs: str = "", mode="w") -> Optional[GLOCS]:
        pricing = self.pricing
        if pricing.status == 1:
            if not pricing.glocs:
                elmp = ELMP()
                elmp_results = elmp.compute_prices(self.allocation, self.scenario, self.configuration, fixed_prices=pricing)
                if elmp_results.status == 1:
                    pricing.glocs = elmp_results.glocs
                else:
                    return None

            if file_glocs:
                file = open(file_glocs, mode)
                file.write(f"GLOCs buyers: {pricing.glocs.glocs_buyers}\n")
                file.write(f"GLOCs sellers: {pricing.glocs.glocs_sellers}\n")
                file.write(f"GLOCs network: {pricing.glocs.glocs_network}\n")
                file.write(f"Total GLOCs: {pricing.glocs.total_glocs}\n")
                file.write("\n")
                file.close()

            return pricing.glocs

        return None

    def compute_llocs(self, file_llocs: str = "", mode="w") -> Optional[LLOCS]:
        pricing = self.pricing
        if pricing.status == 1:
            if not pricing.llocs:
                ip = IP()
                ip_results = ip.compute_prices(self.allocation, self.scenario, self.configuration, fixed_prices=pricing)
                if ip_results.status == 1:
                    pricing.llocs = ip_results.llocs
                else:
                    return None

            if file_llocs:
                file = open(file_llocs, mode)
                file.write(f"LLOCs buyers: {pricing.llocs.llocs_buyers}\n")
                file.write(f"LLOCs sellers: {pricing.llocs.llocs_sellers}\n")
                file.write(f"LLOCs network: {pricing.llocs.llocs_network}\n")
                file.write(f"Total LLOCs: {pricing.llocs.total_llocs}\n")
                file.write("\n")
                file.close()

            return pricing.llocs

        return None

    def compute_mwps(self, file_mwps: str = "", mode="w") -> Optional[MWPS]:
        pricing = self.pricing
        if pricing.status == 1:
            if not pricing.mwps:
                min_mwp = MinMWP()
                min_mwp_results = min_mwp.compute_prices(self.allocation, self.scenario, self.configuration, fixed_prices=pricing)
                if min_mwp_results.status == 1:
                    pricing.mwps = min_mwp_results.mwps
                else:
                    return None

            if file_mwps:
                file = open(file_mwps, mode)
                file.write(f"MWPs buyers: {pricing.mwps.mwps_buyers}\n")
                file.write(f"MWPs sellers: {pricing.mwps.mwps_sellers}\n")
                file.write(f"MWPs network: {pricing.mwps.mwps_network}\n")
                file.write(f"Total MWPs: {pricing.mwps.total_mwps}\n")
                file.write("\n")
                file.close()

            return pricing.mwps

        return None

    def compute_objectives(self, file_objectives: str = "", mode="w") -> Pricing:
        self.compute_glocs(file_glocs=file_objectives, mode=mode)
        self.compute_llocs(file_llocs=file_objectives, mode="a")
        self.compute_mwps(file_mwps=file_objectives, mode="a")

        return self.pricing

    def performance_statistics(self, file_stats: str = "", mode="w") -> Tuple[float, float, float]:
        pricing = self.pricing

        if file_stats:
            f = open(file_stats, mode)
            f.write(f"Runtime in seconds: {pricing.runtime}\n")
            f.write(f"Number of Variables: {pricing.num_vars}\n")
            f.write(f"Number of Constraints: {pricing.num_constrs}\n\n")
            f.close()

        return pricing.runtime, pricing.num_vars, pricing.num_constrs

    def avg_price(self, file_avg: str = "", mode="w") -> float:
        prices = self.pricing.node_prices.values()
        avg = sum(prices) / len(prices) if len(prices) > 0 else 0

        if file_avg:
            file = open(file_avg, mode)
            file.write(f"Average price: {avg}\n\n")
            file.close()

        return avg

    def avg_prices_periods(self, file_plot: str = "", file_avg: str = "", mode="w") -> dict:
        avg_prices = pd.DataFrame(columns=["period", "avg_price"])
        for (_, t), p in self.pricing.node_prices.items():
            avg_prices.loc[len(avg_prices)] = {"period": t, "avg_price": p}

        avg_prices = avg_prices.groupby(["period"]).mean()

        if file_plot:
            plot_avg_prices(avg_prices, self.scenario, file_plot)

        avg_prices_dict = {}
        for period in avg_prices.index.values:
            avg_prices_dict[period] = avg_prices.at[period, "avg_price"]

        if file_avg:
            file = open(file_avg, mode)
            for period, price in avg_prices_dict.items():
                file.write(f"Average price in period {period}: {price}\n")
            file.write("\n")
            file.close()

        return avg_prices_dict

    def avg_node_prices(self, file_avg: str = "", mode: str = "w") -> dict:
        avg_prices = pd.DataFrame(columns=["node", "avg_price"])
        for (v, _), p in self.pricing.node_prices.items():
            avg_prices.loc[len(avg_prices)] = {"node": str(v), "avg_price": p}

        avg_prices = avg_prices.groupby(["node"]).mean()

        avg_prices_dict = {}
        for node in avg_prices.index.values:
            avg_prices_dict[node] = avg_prices.at[node, "avg_price"]

        if file_avg:
            file = open(file_avg, mode)
            for node, price in avg_prices_dict.items():
                file.write(f"Average price at node {node}: {price}\n")
            file.write("\n")
            file.close()

        return avg_prices_dict

    def compute_all_stats_and_plot_data(self, dir_stats: str, pf_model_value) -> None:
        if self.scenario.name != "ARPA":
            plot_supply_demand(dir_stats, self.scenario)

        if isinstance(pf_model_value, ZonalFBMC):
            base_case = getattr(pf_model_value, "base_case_type", "")
            zonal_config = f"{pf_model_value.zonal_configuration}_{base_case}" if base_case else pf_model_value.zonal_configuration
        elif isinstance(pf_model_value, Zonal_NTC):
            factor = getattr(pf_model_value, "factor", None)
            factor_str = f"_f{factor}" if factor is not None else ""
            zonal_config = f"{pf_model_value.zonal_configuration}{factor_str}"
        else:
            zonal_config = ""
        zonal_path = zonal_config + "/" if zonal_config else ""

        path = f"{dir_stats}/{pf_model_value}/{zonal_path}{self.pricing.used_algorithm}_results"
        os.makedirs(path, exist_ok=True)

        file_stats = f"{path}/{self.pricing.used_algorithm}_stats.txt"
        self.compute_objectives(file_objectives=file_stats)
        self.performance_statistics(file_stats=file_stats, mode="a")
        self.avg_price(file_avg=file_stats, mode="a")
        if self.scenario.name != "ARPA":
            self.avg_prices_periods(
                file_plot=f"{path}/{self.pricing.used_algorithm}_prices_periods.png",
                file_avg=file_stats,
                mode="a",
            )
        avg_prices = self.avg_node_prices(file_avg=file_stats, mode="a")

        if self.scenario.name in ["PyPSA_Eur_Large", "PyPSA_Eur_Small"]:
            nodal_scenario = self.base_scenario if zonal_config else self.scenario

            plot_price_heatmap(
                f"{path}/{self.pricing.used_algorithm}_heatmap.png",
                nodal_scenario,
                avg_prices,
                zonal_config,
                power_flow_model=str(pf_model_value),
            )

    def analyse_results(self, folder_results: str, power_flow_model=None):
        """Backwards-compatible wrapper used by the execution chain."""
        self.compute_all_stats_and_plot_data(folder_results, power_flow_model)
        return self.pricing
