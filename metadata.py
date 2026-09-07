"""Builds the series-level metadata table: which BLS series to fetch, with
the industry hierarchy attached as Level 0..N columns for Excel filtering.
"""
import pandas as pd

from hierarchy import industry_paths_frame

DATA_TYPE_CODE = "01"  # ALL EMPLOYEES, THOUSANDS
SEASONAL = "S"  # Seasonally adjusted


def build_metadata(
    series_path: str = "input/ce.series.txt",
    industry_path: str = "input/ce.industry.txt",
) -> pd.DataFrame:
    df = pd.read_csv(series_path, sep="\t")
    df.columns = [c.strip() for c in df.columns]
    df["series_id"] = df["series_id"].str.strip()

    df = df[
        (df["data_type_code"] == DATA_TYPE_CODE) & (df["seasonal"] == SEASONAL)
    ].copy()

    levels = industry_paths_frame(industry_path)
    df = df.merge(levels, on="industry_code", how="left")

    cols = [
        "series_id",
        "series_title",
        "begin_year",
        "begin_period",
        "end_year",
        "end_period",
    ] + list(levels.columns)
    return df[cols].set_index("series_id")
