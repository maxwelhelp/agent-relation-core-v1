#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


CHECKS = [
    [sys.executable, "run_relation_core_eval.py", "--show-failures"],
    [sys.executable, "run_relation_core_redteam.py", "--show-failures"],
    [sys.executable, "run_relation_core_traces.py", "--show-failures"],
    [sys.executable, "run_relation_core_properties.py", "--show-failures"],
    [sys.executable, "run_mcp_adapter_mock.py", "--show-failures"],
]


def main() -> int:
    root = Path(__file__).resolve().parent
    print("=== Agent Relation Core: all checks ===")
    for cmd in CHECKS:
        print("\n$ " + " ".join(cmd))
        res = subprocess.run(cmd, cwd=root)
        if res.returncode != 0:
            print(f"\nFAILED: {' '.join(cmd)}")
            return res.returncode
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
