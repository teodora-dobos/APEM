# Test 3-Node Dataset

Small EU EUPHEMIA test instance for validating zonal ATC and FBMC constraints.

## Structure

- 3 zones (`Z1`, `Z2`, `Z3`)
- 1 period (`t=1`)
- Directed ATC links in `atc.csv`
- FBMC inputs in `fb_constraints.csv` and `fb_ptdf.csv`
- Simple step bids plus one block bid

## Files

- `periods.csv`
- `zones.csv`
- `atc.csv`
- `fb_constraints.csv`
- `fb_ptdf.csv`
- `step_orders.csv`
- `block_orders.csv`
- empty placeholders:
  - `complex_orders.csv`
  - `complex_step_orders.csv`
  - `scalable_complex_orders.csv`
  - `scalable_step_orders.csv`
  - `piecewise_linear_orders.csv`

## Usage

Set in `config.json`:

- `run.market_model = "order_book_based_model"`
- `order_book_based_model.dataset = "TEST_3NODE"`
- `order_book_based_model.euphemia_configuration.network_model = "ATC"` (or `"FBMC"`)

Then run `python main.py`.

