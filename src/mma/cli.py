"""mma: the command line. study/heldout/report/gate read the simulated truth; pipeline commands work
from raw logs only."""

from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mma")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("study", "heldout", "serving", "report", "gate", "all"):
        s = sub.add_parser(c)
        s.add_argument("--profile", default="quick")
        if c in ("serving", "all"):
            s.add_argument(
                "--dsn", default=os.environ.get("MMA_DATABASE_URL"), help="Postgres for the serving benchmark (MMA_DATABASE_URL)"
            )
    a = ap.parse_args(argv)
    if a.cmd == "study":
        from .evaluate.study import run_study

        run_study(a.profile)
    elif a.cmd == "heldout":
        from .evaluate.heldout import run_heldout

        run_heldout(a.profile)
    elif a.cmd == "serving":
        from .evaluate.serving_bench import run

        if not a.dsn:
            print("mma serving needs a Postgres DSN: --dsn or MMA_DATABASE_URL")
            return 2
        run(a.profile, a.dsn)
    elif a.cmd == "report":
        from .evaluate.report import write_reports

        write_reports(a.profile)
    elif a.cmd == "gate":
        from .evaluate.gate import gate

        return 0 if gate(a.profile) else 1
    elif a.cmd == "all":
        from .evaluate.gate import gate
        from .evaluate.heldout import run_heldout
        from .evaluate.report import write_reports
        from .evaluate.study import run_study

        run_study(a.profile)
        run_heldout(a.profile)
        if a.dsn:
            from .evaluate.serving_bench import run

            run(a.profile, a.dsn)
        else:
            print("no MMA_DATABASE_URL: skipping the serving benchmark")
        write_reports(a.profile)
        return 0 if gate(a.profile) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
