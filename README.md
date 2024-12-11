# APEM - Allocation and Pricing in Electricity Markets
![alt text](framework_overview.png)


## Installation
After cloning the code, the following setup steps need to be performed once before running the code.

**Note:** The setup instructions assume a Linux-based or Windows OS and require Python 3.10 (or higher). 

### 1. Virtual environment
- Create a virtual environment (alternatively, you can use `virtualenv` or whatever you prefer) - you can choose any name (e.g., "apem-venv"):
```bash
python -m venv <venv_name>   # Example: python -m venv apem-venv
```

**Note:** You can specify the Python version for the virtual environment, e.g., `python3.11 -m venv <venv_name>`. The specified version already needs to be installed in the system. If you only specify "python3", the venv uses the standard python3 version from the system. When working with _virtualenv_, the command would be _virtualenv - p python3 <venv_name>_.

- Activate the virtual environment:
```bash
# Linux:
source ./<venv-name>/bin/activate   # Example: source ./apem-venv/bin/activate

# Windows: 
<venv-name>\Scripts\activate      # Example: apem_venv\Scripts\activate
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


## Usage
**Note:** Make sure to always activate your virtual environment before running the code!

After setting up the repository, you can run the code by executing the [main.py](./main.py) file with different configurations for the
- **datasets** (currently: ARPA-E, IEEE RTS, PJM, PyPSAEurLarge, and PyPSAEurSmall),
- **power flow models** (currently: DCOPF and Zonal NTC), and
- **pricing algorithms** (currently: ELMP, IP, Join, and Min_MWP).

It is advised to start working with the tuple (PyPSAEurSmall, DCOPF, IP).

```bash
python main.py
```

Once the execution is done, a new `results` folder will be created storing detailed allocation and pricing results.
