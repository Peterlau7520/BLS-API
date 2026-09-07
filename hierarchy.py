
import pandas as pd

# Total private / Goods-producing / Service-providing / Private service-providing
# are alternate aggregate rollups. BLS lists them at display_level 1, directly
# under Total nonfarm, but none of them actually have children in this file --
# the real supersector tree (Mining and logging, Construction, ...) attaches
# directly to Total nonfarm too, right after this quartet. Without excluding
# them from the ancestor stack, the entire detailed industry tree would end up
# nested under "Private service-providing" (the last of the four).
NON_NESTING_ROLLUPS = {5000000, 6000000, 7000000, 8000000}


def build_industry_paths(path: str = "input/ce.industry.txt") -> dict[int, list[str]]:
    """Return {industry_code: [Level 0 name, Level 1 name, ..., own name]}.

    ce.industry.txt has no explicit parent_code column -- the hierarchy is encoded
    as a flattened preorder list via `display_level` (indentation depth) and
    `sort_sequence` (row order). A row's parent is the nearest preceding row with
    a strictly smaller display_level.

    display_level is NOT a stable "this number means this category tier" label --
    it's just how deep the row was indented in BLS's own tree browser at the
    moment it was written down. The same number gets reused for unrelated
    branches once the earlier branch has closed, so you can't match rows by
    level number alone; you have to track which ancestor chain was open when
    each row was reached. That's exactly what a stack gives you for free when
    walking the rows in sort_sequence order:

        Mining and logging                           level 2
        Logging                                      level 5   <- pushed
        Mining, quarrying, and oil and gas extract.  level 3   <- 3 <= 5, pop Logging
        Oil and gas extraction                       level 4   <- pushed
        Mining (except oil and gas)                  level 4   <- 4 <= 4, pop Oil and gas; pushed
        Coal mining                                  level 5   <- pushed

    Logging and Coal mining are both "level 5", but they have nothing to do with
    each other: Logging got popped off the stack as soon as "Mining, quarrying,
    and oil and gas extraction" (level 3) showed up, so by the time Coal mining
    (level 5) is reached, the stack holds a completely different chain of
    ancestors (Mining and logging -> Mining, quarrying... -> Mining except oil
    and gas). The level number 5 is just being recycled for a second, unrelated
    subtree. Whatever is on top of the stack *at that moment* is the real parent
    -- the number by itself is meaningless without that running stack state.
    """
    dfi = pd.read_csv(path, sep="\t")
    dfi.columns = [c.strip() for c in dfi.columns]
    dfi = dfi.sort_values("sort_sequence")

    paths: dict[int, list[str]] = {}
    stack: list[tuple[int, int]] = []  # (display_level, industry_code)

    for _, row in dfi.iterrows():
        code = row["industry_code"]
        name = row["industry_name"].strip()
        level = row["display_level"]

        # Anything on the stack at >= our own level is a closed-off branch
        # (a sibling or a cousin, not an ancestor) -- unwind it first.
        while stack and stack[-1][0] >= level:
            stack.pop()

        # Whatever is left on top is the nearest still-open ancestor.
        parent_path = paths[stack[-1][1]] if stack else []
        paths[code] = parent_path + [name]

        if code not in NON_NESTING_ROLLUPS:
            stack.append((level, code))

    return paths


def industry_paths_frame(path: str = "input/ce.industry.txt") -> pd.DataFrame:
    """Return a DataFrame indexed by industry_code with columns Level 0..N,
    each row's path padded with None past its own depth."""
    paths = build_industry_paths(path)
    max_depth = max(len(p) for p in paths.values())
    level_cols = [f"Level {i}" for i in range(max_depth)]

    data = {
        code: p + [None] * (max_depth - len(p))
        for code, p in paths.items()
    }
    df = pd.DataFrame.from_dict(data, orient="index", columns=level_cols)
    df.index.name = "industry_code"
    return df
