"""
CANARY - deliberately defective analyzer used to validate tools/judge.py.

This file exists only to prove the judge can FAIL something. It reproduces the
exact defects found in this repository's history:

  * returns a clean-looking zero when starved of its declared inputs
  * prints a fully-formed report built from hardcoded demo data when run with
    no input at all
  * reports a severe level with no supporting evidence
  * declares a reduced confidence with no reason
  * varies between runs

A judge that reports this file as PASS is broken. Delete this file once the
judge is trusted - it is scaffolding, not an analyzer.
"""

from __future__ import annotations

import os
import random
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".claude", "complexities"))

from _core import Spec  # noqa: E402

SPEC = Spec(
    id="canary_complexity", sno=99, name="CANARY (defective on purpose)",
    tier="structural", requires=["units", "cfg"],
    summary="Scaffolding to validate the judge. Not a real metric.",
)


def analyze(tree: Dict[str, Any]) -> Dict[str, Any]:
    units = tree.get("units") or []
    # DEFECT: never checks whether cfg is present; happily reports 0.
    total = sum(len((u.get("cfg") or {}).get("children") or []) for u in units)
    return {
        "complexity": SPEC.name,
        "sno": 99,
        "language": tree.get("language", "unknown"),
        # DEFECT: severe level with no items and no hotspots.
        "summary": {"level": "L5", "score": total + random.random(),
                    "headline": f"{total} thing(s)"},
        "metrics": {"units": len(units)},
        # DEFECT: confidence below 1.0 with no reason given.
        "confidence": {"score": 0.5, "reasons": []},
        "hotspots": [],
        "items": [],
    }


if __name__ == "__main__":
    # DEFECT: prints a scored report from hardcoded demo data when given no input.
    import json
    demo = {"language": "java", "units": [{"id": "x", "cfg": {"node_type": "SEQUENCE",
                                                              "children": []}}]}
    print(json.dumps(analyze(demo), indent=2))
