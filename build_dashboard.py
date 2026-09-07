"""Generates dashboard.html: a self-contained interactive time-series
explorer over output.xlsx, with the BLS industry hierarchy as a nav tree.

Reuses hierarchy.py's stack-based tree reconstruction (see that module for
why display_level alone can't be trusted) so the dashboard's nav tree and
api.py's Level 0..N columns are always built the same way.
"""
import json
import re

import pandas as pd

from hierarchy import NON_NESTING_ROLLUPS

OUTPUT_XLSX = "output.xlsx"
SERIES_TXT = "input/ce.series.txt"
INDUSTRY_TXT = "input/ce.industry.txt"
TEMPLATE_HTML = "dashboard_template.html"
DEST_HTML = "dashboard.html"

MONTH_COL_RE = re.compile(r"^\d{4}M\d{2}$")


def month_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if MONTH_COL_RE.match(c)]


def build_series_payload(df: pd.DataFrame, mcols: list[str]) -> dict:
    payload = {}
    for sid, row in df.iterrows():
        vals = row[mcols]
        notna = vals.notna()
        if not notna.any():
            continue
        idx = notna.to_numpy().nonzero()[0]
        lo, hi = idx[0], idx[-1]
        clipped = vals.iloc[lo : hi + 1].round(1).tolist()
        payload[sid] = {
            "title": row["series_title"],
            "start": int(lo),
            "values": clipped,
        }
    return payload


def build_tree(dfi: pd.DataFrame, industry_to_sid: dict, series_payload: dict) -> list:
    dfi = dfi.sort_values("sort_sequence")
    root_children: dict = {}
    stack: list[tuple[int, dict]] = []  # (display_level, children-dict-of-that-node)

    for _, r in dfi.iterrows():
        code = r["industry_code"]
        name = r["industry_name"].strip()
        level = r["display_level"]

        while stack and stack[-1][0] >= level:
            stack.pop()

        parent_children = stack[-1][1] if stack else root_children

        node = {"name": name, "children": {}}
        sid = industry_to_sid.get(code)
        if sid in series_payload:
            node["id"] = sid
        parent_children[code] = node

        if code not in NON_NESTING_ROLLUPS:
            stack.append((level, node["children"]))

    def prune(children: dict) -> list:
        out = []
        for node in children.values():
            kids = prune(node["children"])
            entry = {"name": node["name"]}
            if "id" in node:
                entry["id"] = node["id"]
            if kids:
                entry["children"] = kids
            if "id" in entry or "children" in entry:
                out.append(entry)
        return out

    return prune(root_children)


def build_payload() -> dict:
    df = pd.read_excel(OUTPUT_XLSX, index_col=0)
    mcols = month_columns(df)

    dfs = pd.read_csv(SERIES_TXT, sep="\t")
    dfs.columns = [c.strip() for c in dfs.columns]
    dfs["series_id"] = dfs["series_id"].str.strip()
    dfs = dfs[(dfs["data_type_code"] == "01") & (dfs["seasonal"] == "S")]
    industry_to_sid = dict(zip(dfs["industry_code"], dfs["series_id"]))

    dfi = pd.read_csv(INDUSTRY_TXT, sep="\t")
    dfi.columns = [c.strip() for c in dfi.columns]

    series_payload = build_series_payload(df, mcols)
    tree = build_tree(dfi, industry_to_sid, series_payload)

    return {"months": mcols, "series": series_payload, "tree": tree}


def render_html(payload: dict) -> str:
    blob = json.dumps(payload, separators=(",", ":"))
    blob = blob.replace("</", "<\\/")  # never let a title close the script tag early
    with open(TEMPLATE_HTML, "r", encoding="utf-8") as f:
        template = f.read()
    return template.replace("__DASHBOARD_DATA__", blob)


def count_nodes(nodes: list) -> int:
    n = 0
    for node in nodes:
        n += 1
        n += count_nodes(node.get("children", []))
    return n


def main() -> None:
    payload = build_payload()
    print(f"months: {len(payload['months'])}")
    print(f"series: {len(payload['series'])}")
    print(f"tree nodes: {count_nodes(payload['tree'])}")

    html = render_html(payload)
    with open(DEST_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {DEST_HTML} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
