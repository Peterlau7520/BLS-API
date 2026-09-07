import os
import time
import json
import requests
import pandas as pd

from metadata import build_metadata

# ── Config ─────────────────────────────────────────────────────────────────────
API_KEY    = os.getenv("BLS_API_KEY", "")        # set env var for v2 (recommended)
START_YEAR = 1939
END_YEAR   = 2026
BATCH_SIZE = 50                                  # BLS max series per request
YEAR_CHUNK = 20 if API_KEY else 10              # v2=20yrs, v1=10yrs per request
MAX_RETRIES = 3
API_URL    = (
    "https://api.bls.gov/publicAPI/v2/timeseries/data/" if API_KEY
    else "https://api.bls.gov/publicAPI/v1/timeseries/data/"
)


def year_ranges(start: int, end: int, chunk: int) -> list[tuple[int, int]]:
    out = []
    y = start
    while y <= end:
        out.append((y, min(y + chunk - 1, end)))
        y += chunk
    return out


def fetch(series_ids: list[str], yr_start: int, yr_end: int) -> dict:
    payload: dict = {
        "seriesid": series_ids,
        "startyear": str(yr_start),
        "endyear": str(yr_end),
    }
    if API_KEY:
        payload["registrationkey"] = API_KEY
    resp = requests.post(
        API_URL,
        data=json.dumps(payload),
        headers={"Content-type": "application/json"},
    )
    return json.loads(resp.text)


# ── Load metadata ──────────────────────────────────────────────────────────────
meta = build_metadata()
all_series = meta.index.tolist()

print(f"Loaded {len(all_series)} series from ce.series.txt / ce.industry.txt")
if not API_KEY:
    print("No BLS_API_KEY — using v1 (25 calls/day limit, 10-year chunks)")
    print("Set BLS_API_KEY env var to use v2 and fetch full history in one run.")

# ── Fetch time-series data ─────────────────────────────────────────────────────
all_months = [
    f"{y}M{m:02d}"
    for y in range(START_YEAR, END_YEAR + 1)
    for m in range(1, 13)
]

ts_data: dict[str, dict[str, str]] = {sid: {} for sid in all_series}
ranges = year_ranges(START_YEAR, END_YEAR, YEAR_CHUNK)
total_calls = ((len(all_series) - 1) // BATCH_SIZE + 1) * len(ranges)
call_n = 0

for batch_start in range(0, len(all_series), BATCH_SIZE):
    batch = all_series[batch_start : batch_start + BATCH_SIZE]
    for yr_s, yr_e in ranges:
        call_n += 1
        print(f"[{call_n}/{total_calls}] series {batch_start+1}–{batch_start+len(batch)}, {yr_s}–{yr_e}")

        result = fetch(batch, yr_s, yr_e)
        attempt = 1
        while result.get("status") != "REQUEST_SUCCEEDED" and attempt < MAX_RETRIES:
            attempt += 1
            print(f"  Warning: {result.get('message', 'unknown error')} — retry {attempt}/{MAX_RETRIES}")
            time.sleep(2 ** attempt)
            result = fetch(batch, yr_s, yr_e)

        if result.get("status") != "REQUEST_SUCCEEDED":
            print(f"  Failed after {MAX_RETRIES} attempts: {result.get('message', 'unknown error')} — skipping this batch/range")
            time.sleep(1)
            continue

        for series in result["Results"]["series"]:
            sid = series["seriesID"]
            for dp in series["data"]:
                if "M01" <= dp["period"] <= "M12":
                    ts_data[sid][dp["year"] + dp["period"]] = dp["value"]

        time.sleep(0.5)

# ── Assemble output ────────────────────────────────────────────────────────────
ts_df = pd.DataFrame.from_dict(ts_data, orient="index")
ts_df = ts_df.reindex(columns=all_months)   # enforce chronological order, fill gaps with NaN
ts_df.index.name = "series_id"

output = meta.join(ts_df)
output.to_excel("output.xlsx")
print(f"\nDone — {len(output)} rows × {len(output.columns)} cols → output.xlsx")
