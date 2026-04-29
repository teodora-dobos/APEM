from concurrent.futures import ProcessPoolExecutor
import time
import csv
import argparse
import os
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:  # Minimal fallback if tqdm is unavailable
    def tqdm(iterable, **kwargs):
        return iterable

try:
    import psutil
    process = psutil.Process(os.getpid())
except ImportError:  # Fallback: no process stats available
    psutil = None
    process = None

from power_flow_relaxations.models import DCOPF, Shor, ChordalShor, Jabr, QC
from apem.unit_based_model.data.parsing.parse_arpa import ParseARPA
from apem.execution_chain import Error, _create_configuration
from power_flow_relaxations.utils.network import random_connected_subgraph

try:
    from memory_profiler import memory_usage
    MEMORY_PROFILER_AVAILABLE = True
except ImportError:
    MEMORY_PROFILER_AVAILABLE = False

# Constants
MIP_RELAXATION = True
TOLERANCES: dict = {}
MODELS = [("DCOPF", DCOPF), 
          ("Shor", Shor), 
          ("ChordalShor", ChordalShor), 
          ("Jabr", Jabr)
          ] + [
            (f"QC{degree}", (QC, degree)) for degree in [4, 6, 8, 10, 12]
          ] + [
              (f"QC{degree}_Global", (QC, ("global", degree))) for degree in [4, 6, 8, 10, 12]
          ]

def parse_args():
    parser = argparse.ArgumentParser(description='Run relaxation experiments')
    parser.add_argument('--batch-size', type=int, default=1, 
                       help='Number of scenarios per batch (default: 1)')
    parser.add_argument('--model-start-index', type=int, default=0,
                       help='Starting index for models to run (default: 0)')
    parser.add_argument('--model-end-index', type=int, default=-1,
                       help='Ending index for models to run (default: -1)')
    parser.add_argument('--scenario-start-index', type=int, default=0,
                       help='Starting index for scenarios to run (default: 0)')
    parser.add_argument('--scenario-end-index', type=int, default=-1,
                       help='Ending index for scenarios to run (default: -1)')
    parser.add_argument('--model', type=str, default='all',
                       help='Model to run (default: all)')
    return parser.parse_args()

def log_memory():
    if process is None:
        return
    mem = process.memory_info().rss / (1024**2)  # MB
    print(f"[{time.strftime('%H:%M:%S')}] Memory usage: {mem:.2f} MB")

def run_model(args):
    subscenario, model_class = args
    if isinstance(model_class, tuple):
        model_class, degree = model_class
        if isinstance(degree, tuple):
            sampling_mode, degree = degree
        else:
            sampling_mode = "local"
    else:
        degree = None
        sampling_mode = None

    configuration = _create_configuration()
    configuration.relaxation = MIP_RELAXATION

    if model_class == QC:
        if sampling_mode == "global":
            model = model_class(subscenario, configuration, degree=degree, tolerances=TOLERANCES, local_sampling=False)
        else:
            model = model_class(subscenario, configuration, degree=degree, tolerances=TOLERANCES)
    else:
        model = model_class(subscenario, configuration, tolerances=TOLERANCES)

    log_memory()

    def _solve():
        return model.solve()

    if MEMORY_PROFILER_AVAILABLE:
        # Track memory usage during model.solve(), report increase over baseline
        start_time = time.time()
        mem_usage, allocation = None, None
        try:
            baseline = memory_usage(-1, interval=0.1, timeout=1)[0]  # Current process RSS in MiB
            mem_usage = memory_usage((_solve,), max_usage=True, retval=True, interval=0.1, timeout=None)
            # memory_usage returns (max_mem, retval) if max_usage=True and retval=True
            if isinstance(mem_usage, tuple):
                peak_memory, allocation = mem_usage
            else:
                peak_memory = mem_usage
                allocation = None
            elapsed_time = time.time() - start_time
        except Exception as e:
            print(f"Model {model_class.__name__} failed on subscenario with error: {e}")
            return None, None, None, None, {}
        # memory_profiler reports in MiB
        peak_memory_mb = peak_memory - baseline
    else:
        # Fallback: psutil snapshot before/after (not true peak)
        peak_memory = process.memory_info().rss if process is not None else 0
        try:
            start_time = time.time()
            allocation = model.solve()
            elapsed_time = time.time() - start_time
            if process is not None:
                current_mem = process.memory_info().rss
                if current_mem > peak_memory:
                    peak_memory = current_mem
        except Exception as e:
            print(f"Model {model_class.__name__} failed on subscenario with error: {e}")
            return None, None, None, None, {}
        peak_memory_mb = peak_memory / (1024 ** 2)

    solve_time = getattr(model, 'solve_time', None)
    if isinstance(allocation, Error):
        print(f"Model {model_class.__name__} failed on subscenario with error: {allocation} {allocation._status}")
        return None, elapsed_time, solve_time, peak_memory_mb, {}

    violations = allocation.compute_feasibility_violations(print_summary=False)
    welfare = allocation.compute_welfare()
    return welfare, elapsed_time, solve_time, peak_memory_mb, violations

if __name__ == "__main__":
    args = parse_args()
    
    arpa = ParseARPA().parse_data()

    def build_subscenario(base_scenario, nodes, r_star):
        """Create a Scenario restricted to a set of nodes."""
        network = base_scenario.network.copy().subgraph(nodes).copy()
        df_buyers = base_scenario.df_buyers.copy()
        df_sellers = base_scenario.df_sellers.copy()
        df_buyers = df_buyers[df_buyers["node"].isin(nodes)]
        df_sellers = df_sellers[df_sellers["node"].isin(nodes)]

        # recompute nodes_agents to match filtered nodes
        sellers_by_node = df_sellers.groupby("node")["seller"].apply(list).to_dict()
        buyers_by_node = df_buyers.groupby("node")["buyer"].apply(list).to_dict()
        nodes_agents = {
            node: {
                "sellers": sellers_by_node.get(node, []),
                "buyers": buyers_by_node.get(node, []),
            }
            for node in network.nodes
        }

        return base_scenario.__class__(
            name=base_scenario.name,
            df_buyers=df_buyers,
            df_sellers=df_sellers,
            network=network,
            nodes_agents=nodes_agents,
            periods=base_scenario.periods,
            blocks_buyers=base_scenario.blocks_buyers,
            blocks_sellers=base_scenario.blocks_sellers,
            r_star=r_star,
        )

    def get_random_valid_subscenarios(n_nodes, n_graph, max_attempts=2000):
        network_size = len(arpa.network.nodes)
        if n_nodes > network_size:
            print(f"[warn] Requested subgraph with {n_nodes} nodes, but network has only {network_size}; skipping.")
            return []

        valid_subscenarios = []
        seed = 0
        attempts = 0
        for _ in range(n_graph):
            valid_subscenario = False
            while not valid_subscenario and attempts < max_attempts:
                attempts += 1
                seed += 1
                try:
                    subnetwork = random_connected_subgraph(arpa.network, n_nodes=n_nodes, seed=seed)
                except ValueError:
                    break  # not enough connected nodes with this size
                subscenario = build_subscenario(arpa, nodes=subnetwork, r_star=next(iter(subnetwork)))
                valid_subscenario = (
                    subscenario.df_sellers["seller"].nunique() > 0
                    and subscenario.df_buyers["buyer"].nunique() > 0
                    and subscenario.network.number_of_nodes() > 0
                )
            if valid_subscenario:
                valid_subscenarios.append(subscenario)
            else:
                print(f"[warn] Unable to build a valid subscenario with {n_nodes} nodes after {attempts} attempts.")

        return valid_subscenarios

    subscenarios = []
    for n in range(1, 21):
        subs = get_random_valid_subscenarios(n_nodes=32 * n, n_graph=args.batch_size)
        if subs:
            subscenarios.append(subs)
        else:
            print(f"[warn] Skipping subscenario size {32 * n} (no valid samples).")

    os.makedirs("relaxation_results", exist_ok=True)
    if args.model_end_index > len(MODELS) or args.model_end_index < 0:
        args.model_end_index = len(MODELS)

    if args.scenario_end_index > len(subscenarios) or args.scenario_end_index < 0:
        args.scenario_end_index = len(subscenarios)

    if args.model != 'all':
        tags: list[str] = [tag.strip().lower() for tag in args.model.split(',')]
        models = [(tag, model) for tag, model in MODELS if tag.lower() in tags]
    else:
        models = MODELS[args.model_start_index:args.model_end_index]

    print("Running relaxations with the following parameters:")
    print(f"Batch size: {args.batch_size}")
    print(f"Subscenario sizes: {', '.join([str(32 * (i + 1)) for i in range(args.scenario_start_index, args.scenario_end_index)])}")
    print(f"Models: {', '.join([tag for tag, _ in models])}")

    for tag, model in models:
        for scenario_index in range(args.scenario_start_index, args.scenario_end_index):
            arg_list = [(subscenarios[scenario_index][batch_index], model) for batch_index in range(args.batch_size)]

            try:
                with ProcessPoolExecutor(max_workers=1) as executor:
                    scenario_results = list(tqdm(executor.map(run_model, arg_list), total=len(arg_list), desc=f"Running {tag} on subscenario of sizes {32 * (scenario_index + 1)}..."))
            except PermissionError:
                # Fallback in restricted environments: run sequentially
                scenario_results = [run_model(run_args) for run_args in tqdm(arg_list, total=len(arg_list), desc=f"Running {tag} on subscenario of sizes {32 * (scenario_index + 1)}...")]

            with open(f"relaxation_results/{tag}_{32 * (scenario_index + 1)}_results.csv", "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                for i, stats in enumerate(scenario_results):
                    welfare, elapsed_time, solve_time, peak_memory, violations = stats
                    if csvfile.tell() == 0:
                        writer.writerow(["batch_index", "welfare", "elapsed_time", "solve_time", "peak_memory_usage"] + list(violations.keys()))
                    writer.writerow([i, welfare, elapsed_time, solve_time, peak_memory] + list(violations.values()))
