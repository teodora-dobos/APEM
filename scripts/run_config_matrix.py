"""
Utility to run a matrix of APEM configurations to sanity‑check the pipeline.

Current matrix:
- Datasets: IEEE_RTS, PJM, PyPSAEurSmall, PyPSAEurLarge, ARPA
- Models per dataset:
  * DCOPF: all datasets
  * Zonal_NTC_aggregated: PyPSA datasets only (default zonal_DE4, factor 0.8)
  * Zonal_NTC_multiedge: PyPSA datasets only (default zonal_DE4, factor 0.8)
  * Zonal_FBMC: PyPSA datasets only, base cases BC1–BC4 (zonal_DE4)

Defaults: IP pricing, MinCostRD redispatch, MPLCONFIGDIR set to a local cache if unset.
"""


import os
import sys
import traceback
from pathlib import Path
from typing import Iterable, Tuple

# Ensure repo root is on sys.path when run directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apem.execution_chain import solve_and_analyse_scenario
from apem.enums import MarketModels, PricingAlgorithms, RedispatchAlgorithms, US_Datasets, FBMCBaseCases
from apem.US_market_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_ntc_aggregated import Zonal_NTC_aggregated
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_ntc_multiedge import Zonal_NTC_multiedge
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_fbmc_included import ZonalFBMC
from apem.US_market_model.data.parsing.scenario import Scenario


def _ensure_matplotlib_dir() -> None:
    """Set MPLCONFIGDIR to a writable path if not already set (avoids font cache errors)."""
    if "MPLCONFIGDIR" not in os.environ:
        cache_dir = os.path.join(os.getcwd(), ".matplotlib_cache")
        os.makedirs(cache_dir, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = cache_dir


def run_single(
    dataset: US_Datasets,
    power_flow_model,
    pricing_algorithm: PricingAlgorithms = PricingAlgorithms.IP,
    redispatch_algorithm: RedispatchAlgorithms = RedispatchAlgorithms.MinCostRD,
    redispatch_constraint_units: bool = False,
    redispatch_threshold: float = 0.001,
    alpha: float = 0.0,
) -> None:
    """Run one configuration through solve_and_analyse_scenario."""
    _ensure_matplotlib_dir()
    solve_and_analyse_scenario(
        US_dataset=dataset,
        EU_dataset=dataset,  # unused for US_model but required by signature
        market_model=MarketModels.US_model,
        power_flow_model=power_flow_model,
        cut_type=None,  # unused for US_model
        pricing_algorithm=pricing_algorithm,
        redispatch_algorithm=redispatch_algorithm,
        redispatch_constraint_units=redispatch_constraint_units,
        redispatch_threshold=redispatch_threshold,
        alpha=alpha,
    )


def _matrix() -> Iterable[Tuple[US_Datasets, Scenario]]:
    """Return the dataset list to test."""
    return [
        US_Datasets.IEEE_RTS,
        US_Datasets.PJM,
        US_Datasets.PyPSAEurSmall,
        US_Datasets.PyPSAEurLarge,
        US_Datasets.ARPA,
    ]


def main():
    _ensure_matplotlib_dir()
    runs = []

    # Base cases for Zonal_FBMC
    base_cases = [bc.value for bc in FBMCBaseCases]

    pypsa_datasets = {US_Datasets.PyPSAEurSmall, US_Datasets.PyPSAEurLarge}

    for dataset in _matrix():
        # Nodal DCOPF always
        runs.append((dataset, DCOPF()))

        if dataset in pypsa_datasets:
            # Zonal NTC variants with default factor from enums/config
            runs.append((dataset, Zonal_NTC_aggregated(zonal_configuration="zonal_DE4", factor=0.8)))
            runs.append((dataset, Zonal_NTC_multiedge(zonal_configuration="zonal_DE4", factor=0.8)))

            # Zonal FBMC with multiple base cases
            for bc in base_cases:
                runs.append((dataset, ZonalFBMC(zonal_configuration="zonal_DE4", base_case_type=bc)))

    successes, failures = [], []
    for idx, (dataset, pf_model) in enumerate(runs, start=1):
        print(f"[{idx}/{len(runs)}] Running {dataset.name} with {pf_model}...")
        try:
            run_single(dataset, pf_model)
            successes.append((dataset, pf_model))
            print(f"✔ Success: {dataset.name} | {pf_model}")
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            failures.append((dataset, pf_model, exc))
            print(f"✖ Failed: {dataset.name} | {pf_model} | {exc}")

    print("\n=== Summary ===")
    print(f"Successes: {len(successes)}")
    print(f"Failures: {len(failures)}")
    if failures:
        for dataset, pf_model, exc in failures:
            print(f"- {dataset.name} | {pf_model} -> {exc}")


if __name__ == "__main__":
    main()
