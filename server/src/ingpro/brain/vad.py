"""Loads the Warriner/Kuperman/Brysbaert (2013) valence-arousal-dominance norms (content/vocab/warriner_vad.csv,
gitignored: CC BY-NC-ND, not redistributed with the repo — see scripts/setup.sh for how to fetch it).

Each lemma maps to (valence, arousal, dominance) on the source's own 1-9 scale: valence = how pleasant/unpleasant,
arousal = how calming/exciting, dominance = how in-control/out-of-control the word feels.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_vad(content_dir: Path) -> dict[str, tuple[float, float, float]]:
    path = content_dir / "vocab" / "warriner_vad.csv"
    if not path.is_file():
        return {}
    out: dict[str, tuple[float, float, float]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            word = row.get("Word", "").strip().lower()
            try:
                out[word] = (float(row["V.Mean.Sum"]), float(row["A.Mean.Sum"]), float(row["D.Mean.Sum"]))
            except (KeyError, ValueError):
                continue
    return out
