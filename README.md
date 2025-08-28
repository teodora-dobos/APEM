# APEM - Allocation and Pricing in Electricity Markets
![alt text](framework_overview.png)


## Installation
<details>
  <summary> After cloning the code, the following setup steps need to be performed once before running the code. </summary>

  <br>**Note:** The setup instructions assume a Linux-based or Windows OS and require Python 3.10 (or higher). 

  ### 1. Virtual environment
  - Create a virtual environment (alternatively, you can use `virtualenv` or whatever you prefer) - you may choose any name (e.g., "apem-venv"):
  ```bash
  python -m venv <venv_name>   # Example: python -m venv apem-venv
  ```

  **Note:** You can specify the Python version for the virtual environment, e.g., `python3.11 -m venv <venv_name>`. The specified version already needs to be installed in the system. If you only specify "python3", the venv uses the standard python3 version from the system. When working with _virtualenv_, the command would be _virtualenv - p python3 <venv_name>_.

  - Activate the virtual environment:
  ```bash
  # Linux:
  source ./<venv-name>/bin/activate        # Example: source ./apem-venv/bin/activate

  # Windows: 
  source <venv-name>/Scripts/activate      # Example: source apem-venv/Scripts/activate
  ```

  **Note:** The virtual environment can be deactivated using `deactivate`- however, for the next steps, we want the virtual environment to be active.


  ### 2. Install required packages
  - Install all requirements from the `requirements.txt` file:
  ```bash
  pip install -r <path-to-requirements.txt>   # Example: pip install -r requirements.txt
  ```

  ### 3. Gurobi license
  To run the code, a valid academic or commercial Gurobi license is required ([more information](https://gurobi.com/unrestricted)).
  - If you do not already have such a license, you first need to create one together with API keys: 
    - Log into the Gurobi [user portal](https://portal.gurobi.com/iam/home/) > Licenses > Request > Choose your license (for academic, you can either use _WLS Academic_ - e.g., required when using WSL - or _Named-User Academic_) > Generate Now! &rarr; license is now listed under "Licenses"
    - Open Gurobi [Web License Manager](https://license.gurobi.com/manager/licenses/) > API Keys > Create API Key (make sure you create them for your new license: check ID) > Download keys
  - Finally place the `gurobi.lic` file in your `home directory`
</details>

## Usage
**Note:** Make sure to always activate your virtual environment before running the code!

Before running the code, update the [`config.json`](./config.json) file to create a configuration that will be run.

The most important section is `scenario`, which defines the dataset, market model, power flow model, pricing, and redispatch algorithm.

```jsonc
"scenario": {
    "market_model": "EU_model",    // choose from _available_market_models
    "US_dataset": "ARPA",          // choose from _available_US_datasets
    "EU_dataset": "GME",           // choose from _available_EU_datasets
    "power_flow_model": {
        "type": "DCOPF"            // choose from _available_power_flow_models
    },
    "cut_type": "price based",     // choose from _available_cut_types
    "pricing_algorithm": "IP",     // choose from _available_pricing_algorithms
    "redispatch_algorithm": "MinCostRD"  // choose from _available_redispatch_algorithms 
}
```

### Available options

- **Market models**: `US_model`, `EU_model`
- **Datasets**
  - US: `IEEE_RTS`, `PJM`, `PyPSAEurSmall`, `PyPSAEurLarge`, `ARPA`
  - EU: `Generated Small`, `Generated Large`, `OMIE`, `GME`, `IEEE_RTS`, `ARPA`, `PyPSAEurSmall`, `PyPSAEurLarge`, `PJM`
- **Power flow models** (only for ``US_model``): `DCOPF`, `Zonal_NTC`
- **Cut types** (only for `EU_model`): `price based`, `combinatorial benders`, `no good`
- **Pricing algorithms** (only for `US_model`): `ELMP`, `IP`, `MinMWP`, `Join`
- **Redispatch algorithms** (only for `US_model/Zonal_NTC`): `MinCostRD`, `MinVolRD`
- **Zonal configurations** (only for `US_model/Zonal_NTC`): `national`, `zonal_DE2-k`, `zonal_DE2-s`, `zonal_DE3`, `zonal_DE4`, `zonal_DE4-refined`, `zonal_DE5`

Other global settings like solver tolerances and runtime limits can be adjusted under `"solver_configuration"`. Zonal-specific settings are under `"zonal_configuration"`.

---
To run the configuration, execute:
```bash
python main.py
```

Once the execution is done, a new `results` folder will be created storing detailed allocation and pricing results.

**Note:** If you ever run into the error "ModuleNotFoundError: No module named 'src'", this can likely be resolved by setting the PYTHONPATH inside your virtual environment. To do this, add the following line to <venv_name>/bin/activate: `export PYTHONPATH=/<path-to-APEM>`.
