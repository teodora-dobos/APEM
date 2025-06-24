# OMIE Day-Ahead Order Dataset

This dataset combines two official OMIE sources, e.g.:

- `CAB_20250325.1`: Header information for each offer ("cabecera")
- `DET_20250325.1`: Detailed price/quantity records for each offer and market hour

These files are formatted according to OMIE’s public specification (Version 1.36, March 2025) and merged via the `cod_oferta` (Offer ID).

---

## Source Overview

| Source File       | Description |
|-------------------|-------------|
| `CAB_YYYYMMDD.1`  | Header metadata: unit, offer type, fixed/variable costs, etc. |
| `DET_YYYYMMDD.1`  | Detailed price/volume points per offer and time period |

---

## Final Column Descriptions

### From `DET` (Offer Details)

| Column       | Description |
|--------------|-------------|
| `cod_oferta` | Offer ID, primary key for merge |
| `version_x`  | Offer version from detail file |
| `periodo`    | Hour of the day (1–24, possibly up to 25) |
| `num_block`  | Block offer ID (`0` = not a block offer) |
| `num_tramo`  | Sub-offer number (price step) |
| `grupo_excl` | Exclusive group ID (`≠ 0` means part of an exclusive group) |
| `precio`     | Offered price (EUR/MWh) |
| `cantidad`   | Quantity (MW) |
| `mav`        | Minimum Acceptable Volume (used in SCOs) |
| `mar`        | Minimum Acceptance Ratio (used in block orders) |

### From `CAB` (Offer Header)

| Column         | Description                                               |
| -------------- | --------------------------------------------------------- |
| `version_y`    | Offer version from header file                            |
| `cod_uof`      | Code of the offering unit                                 |
| `unidad`       | Name of the unit submitting the offer                     |
| `cv`           | Offer type: `V` = sell, `C` = buy                         |
| `ofer_plazo`   | Long-term origin: `O` = normal, `P` = long-term breakdown |
| `fijo_eur`     | Fixed cost component (EUR)                                |
| `potencia_max` | Maximum power for the unit (MW)                           |
| `cod_int`      | Interconnection code (only for interconnect offers)       |
| `timestamp`    | Offer submission timestamp (YYMMDDHHMMSS)                 |

---

## How to Use This Dataset

- Identify **Block Orders** using `num_block ≠ 0`
- Find **Exclusive Block Groups** via `grupo_excl ≠ 0`
- Filter **Scalable Complex Orders (SCO)** with `mav > 0` and `fijo_eur > 0`
- Distinguish buy/sell using `cv` (`V` = sell, `C` = buy)
- Analyze pricing structures across `num_tramo` steps per `cod_oferta`