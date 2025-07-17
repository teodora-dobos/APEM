# EUPHEMIA (Pan-European Hybrid Electricity Market Integration Algorithm)

### Quick Start
For a quick start run the method `solve_euphemia(dataset, cutting_strategy)` from `execution_chain.py`
Parameters:
- dataset: choose from `Datasets`
- cutting_stratgey: choose a cutting strategy from `CutType` (NG=No-Good, CB=Combinatorial-Benders, PB=Price-Based)

You can also run the algorithm without these parameters, then the base configuration will be used ("Generated Small", Price-based cutting)

### Config
You can customize Euphemia by creating and modifying a `EuphemiaConfig` object from `euphemia_config.py`
A config object can be used to initialize a new `MasterProblem` object that is the foundation of each Euphemia run.

Methods:

`set_dataset(dataset: Datasets)`: Load and parses a specific dataset. Should be used to set the dataset.


Below are the key attributes and what they control:

| Parameter                     | Description                                                                                                                                                                 |
|-------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `scenario`                    | Parsed scenario data; initialized by the selected dataset. Default: `Datasets.GENERATED_SMALL`                                                                              |
| `disable_reinsertion`         | If `True`, disables the automatic reinsertion process for rejected bids.                                                                                                    |
| `price_lower_bound`           | Lower bound for price values during optimization (default: -500).                                                                                                           |
| `price_upper_bound`           | Upper bound for price values during optimization (default: 4000).                                                                                                           |
| `beta_MIC`                    | Controls how much a paradoxically accepted MIC order must be out-of-the-money (OTM).                                                                                        |
| `delta_load_gradient`         | Threshold for allowing paradoxically accepted load gradients.                                                                                                               |
| `epsilon`                     | Small numerical tolerance used to mitigate floating-point precision issues (e.g., in Gurobi).                                                                               |
| `max_iterations`              | Sets a hard cap on the number of iterations during the solving process (default: 50).                                                                                       |
| `cutting_strategy`            | Strategy used to generate cuts during the algorithm. Values come from `CutType` enum (e.g., `CutType.CB` for callback-based cuts).                                          |
| `delta_PAB`                   | Placeholder parameter (currently unused) related to Paradoxically Accepted Blocks.                                                                                          |
| `calculate_corrected_welfare` | Adds an additional welfare value to the evaluation output (important for US data). The surplus of inelastic demand is dedcuted from the welfare (Only works for 24 periods!) |

### Evaluation
Statistics about an Euphemia run are stored in `euphemia_results/evaluation/evaluation.txt`

### Conversion (US-EU bidding language)
The main method in `run_us_eu_conversion.py` can be modified and used to run the conversion with different parameters. Here, you can also set
if patterns should be generated and what compression methods should be applied to the data.