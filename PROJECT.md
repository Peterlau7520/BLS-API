# BLS CE Employment Pipeline

Pulls "All Employees, Thousands, Seasonally Adjusted" (data type `01`, seasonal `S`)
series from the BLS Current Employment Statistics (CE) program, attaches each
series' full industry hierarchy, and writes one Excel file with a `Level 0..N`
column per depth so the sheet can be filtered/grouped natively in Excel. A
second stage turns that same data into a self-contained interactive HTML
dashboard for browsing the time series without opening Excel.

## Flow

```
input/ce.industry.txt ──┐
                         ├─> hierarchy.py  ──> industry_code -> [Level 0, Level 1, ...]
                         │
input/ce.series.txt ────┴─> metadata.py   ──> one row per series_id, with
                                               Level 0..N columns attached
                                                     │
                                                     v
                                                  api.py
                                     (fetches monthly history per series
                                      from the BLS API, joins onto metadata)
                                                     │
                                                     v
                                               output.xlsx
                                                     │
                                                     v
                                          build_dashboard.py + dashboard_template.html
                                                     │
                                                     v
                                               dashboard.html
```

## Files

- **`input/`** — raw BLS reference flat files, unmodified as downloaded:
  - `ce.series.txt` — one row per series_id, with its industry_code/data_type_code/seasonal flags.
  - `ce.industry.txt` — one row per industry_code, with `display_level` (indentation depth) and `sort_sequence` (display order). No explicit parent column — see `hierarchy.py`.
  - `ce.datatype.txt` — lookup for `data_type_code` (`01` = All Employees, Thousands).

- **`hierarchy.py`** — reconstructs the industry tree from `ce.industry.txt`'s `display_level`/`sort_sequence` using a stack (see the module docstring on `build_industry_paths` for why level numbers alone don't tell you the tree shape). Exposes:
  - `build_industry_paths()` → `{industry_code: [Level 0 name, ..., own name]}`
  - `industry_paths_frame()` → same thing as a DataFrame indexed by `industry_code`, columns `Level 0..N`, padded with `None` past each row's own depth.

- **`metadata.py`** — filters `ce.series.txt` down to the series we care about (`data_type_code == "01"`, `seasonal == "S"`) and merges in the `Level 0..N` columns from `hierarchy.py`. `build_metadata()` returns one row per `series_id` — this is the full list of series `api.py` fetches, plus the columns that go straight into the output sheet.

- **`api.py`** — entry point. Loads `build_metadata()`, batches the series through the BLS `timeseries/data` API (`BATCH_SIZE` series x `YEAR_CHUNK` years per call, retrying failed calls up to `MAX_RETRIES` times), reindexes each series to a full `YYYYMMM` calendar, joins the monthly values onto the metadata, and writes `output.xlsx` — then calls `build_dashboard.main()` directly, so `dashboard.html` is always regenerated from the `output.xlsx` that was just written.
  - Reads `BLS_API_KEY` from the environment (`.env`) — with a key you get the v2 endpoint (20-year chunks, higher daily limit); without one it falls back to v1 (10-year chunks, 25 calls/day).

- **`output.xlsx`** — the pipeline's output: one row per series, `Level 0..N` industry columns followed by one column per month.

- **`build_dashboard.py`** — reads `output.xlsx` plus `input/ce.series.txt`/`input/ce.industry.txt`, and:
  - clips each series to its own non-null date range and rounds to 1 decimal (BLS seasonally-adjusted "thousands" values aren't always whole numbers),
  - rebuilds the same industry tree as `hierarchy.py` (reusing its `NON_NESTING_ROLLUPS` exception) but keyed by `industry_code` so it can attach each node's `series_id` and prune the handful of industries with no seasonally-adjusted series of their own,
  - injects the result as JSON into `dashboard_template.html` (marker `__DASHBOARD_DATA__`) and writes `dashboard.html`.
  - `api.py` calls `build_dashboard.main()` automatically after writing `output.xlsx`. Run it standalone (e.g. to pick up a template/style edit without re-fetching from the API) with `python build_dashboard.py` — it only reads the `output.xlsx` already on disk.

- **`dashboard_template.html`** — the dashboard's HTML/CSS/JS shell (hand-rolled SVG line chart, no external chart library). Left rail is a searchable tree over every industry node; clicking one plots its full monthly history. Supports comparing up to 8 series at once, a Levels/Indexed(=100) toggle (needed because "Total nonfarm" and a detailed leaf industry differ by orders of magnitude — see `dataviz` skill's dual-axis anti-pattern), a zoom/pan brush, hover tooltip, and a data-table twin of the chart.

- **`dashboard.html`** — generated; self-contained (all ~842 series embedded as JSON, only Google Fonts loaded externally). Open it directly in a browser — no server needed.

- **`requirements.txt`** — pinned dependencies for the venv in `bls/`.

- **`deprecated/`** — superseded exploration, kept for reference only, not read by any current code:
  - `parse.ipynb` — the original notebook prototype for the hierarchy logic now in `hierarchy.py`/`metadata.py`.
  - `result.xlsx` — `parse.ipynb`'s output; predecessor to `output.xlsx`.
  - `series_ids.xlsx`, `test.xlsx` — early one-off experiments.
  - `bls_tree_table.html (nyvkvc).html (nyvkvc).html` — an earlier standalone HTML prototype for visualizing the hierarchy (unrelated to the current pipeline).

## Running it

```
bls\Scripts\activate
python api.py
```

(PowerShell: `bls\Scripts\Activate.ps1`. Git Bash: `source bls/Scripts/activate`.)

Set `BLS_API_KEY` (see `.env`) beforehand to use the faster v2 API path. `api.py` writes both `output.xlsx` and `dashboard.html` in one run — open `dashboard.html` directly in a browser afterward.
