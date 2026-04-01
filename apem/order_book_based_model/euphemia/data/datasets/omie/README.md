
# OMIE Day-Ahead Market File Format: `cab` and `det` Files

This README provides descriptions of the columns found in the `cab_aaaammdd.v` (header) and `det_aaaammdd.v` (detail) files as published by OMIE for the Day-Ahead Electricity Market.
Note that the format is very likely to change in 2025 with the introduction of 15min periods.

---

## `cab_aaaammdd.v` – Header File

Each row represents a unique offer unit that entered the market coupling process. All fields are in fixed positions.

| Column Name       | Description                                           | Format   | Position |
|-------------------|-------------------------------------------------------|----------|----------|
| `CodOferta`       | Offer code (unique identifier)                        | Integer  | 1        |
| `Version`         | Offer version number                                  | Integer  | 8        |
| `Código Unidad`   | Identifier of the bidding unit                        | String   | 11       |
| `Descripción`     | Description of the bidding unit                       | String   | 18       |
| `CV`              | Indicates if it's a purchase (`C`) or sale (`V`)      | Char     | 48       |
| `Int`             | Not used                                              | Char     | 49       |
| `OferPlazo`       | Offer type: Normal (`O`) or from contract disaggregation (`P`) | Char     | 50       |
| (Unused)          | Reserved fields, not used                             | Float    | 51-67    |
| `MaxRamSub`       | Maximum ramp-up                                       | Float    | 85       |
| `MaxRamBaj`       | Maximum ramp-down                                     | Float    | 92       |
| `Fijoeuro`        | Fixed cost in EUR (from 1/6/2010)                     | Float    | 99       |
| `Vareuro`         | Variable cost in EUR/MWh (from 1/6/2010)              | Float    | 116      |
| `MaxPot`          | Maximum power (MW)                                    | Float    | 133      |
| `MaxRamArr`       | Max ramp for startup                                  | Float    | 140      |
| `MaxRamPar`       | Max ramp for shutdown                                 | Float    | 147      |
| `CodInt`          | Interconnection code                                  | Integer  | 154      |
| `Año`             | Year of offer insertion                               | Integer  | 156      |
| `Mes`             | Month of offer insertion                              | Integer  | 160      |
| `Día`             | Day of offer insertion                                | Integer  | 162      |
| `Hora`            | Hour of offer insertion                               | Integer  | 164      |
| `Minuto`          | Minute of offer insertion                             | Integer  | 166      |
| `Segundo`         | Second of offer insertion                             | Integer  | 168      |

---

## `det_aaaammdd.v` – Detail File

Each row represents one price-quantity block of a previously defined offer.

| Column Name       | Description                                                                 | Format   | Position |
|-------------------|-----------------------------------------------------------------------------|----------|----------|
| `CodOferta`       | Offer code (must match a code from the `cab` file)                          | Integer  | 1        |
| `Version`         | Version number (must match the version in the `cab` file)                   | Integer  | 8        |
| `Período`         | Market period (hour of day: 1–24 or 1–25)                                   | Integer  | 11       |
| `NumBloq`         | Block number within the period                                              | Integer  | 13       |
| (Unused)          | Reserved field                                                              | Float    | 15       |
| `PrecEuro`        | Price in EUR/MWh                                                            | Float    | 32       |
| `Energía`         | Energy quantity (MWh)                                                       | Float    | 49       |
| `BloqInd`         | Indicates if block is divisible: `S` (Yes), `N` (No)                        | Char     | 56       |
| `BloqRet`         | Indicates if block is withdrawable: `S` (Yes), `N` (No)                     | Char     | 57       |
