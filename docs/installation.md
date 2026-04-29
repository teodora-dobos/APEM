# Installation

This page shows the recommended local setup for APEM. The goal is to get a clean Python environment, install the package, and make sure the solver setup is in place.

## Before You Start

You will need:

- Python 3.10 or newer
- `git`
- a virtual environment tool (`venv` is enough)
- a valid [Gurobi](https://www.gurobi.com/) license for optimization runs

## 1. Clone The Repository

```bash
git clone https://github.com/teodora-dobos/APEM.git
cd APEM
```

## 2. Create A Virtual Environment

```bash
python -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

## 3. Install Dependencies

Install the runtime dependencies and the package itself:

```bash
pip install -r requirements.txt
pip install -e .
```

The editable install makes sure local source-code changes are picked up immediately.

## 4. Configure Gurobi

APEM uses [Gurobi](https://www.gurobi.com/) for its optimization workflows. Make sure:

- Gurobi is installed in the same Python environment
- your license is available on the machine

If your environment does not already include `gurobipy`, install it with:

```bash
pip install gurobipy
```

Then verify that your license is active before running larger workflows.

## 5. Verify The Installation

From the repository root, run:

```bash
python -c "import apem; print('APEM import successful')"
```

If that works, the Python package is installed correctly.

## Next Step

After installation, continue with the configuration page and then choose the workflow you want to run.
