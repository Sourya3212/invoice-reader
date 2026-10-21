"""Command line.

    python -m invoice_reader run  --docs data/docs --backend rules  --out results/rules
    python -m invoice_reader run  --docs data/docs --backend ollama --out results/ollama [--model qwen3.5:9b]
    python -m invoice_reader eval --pred results/rules --truth data/truth --manifest data/manifest.csv
"""
import argparse
import sys

from . import evaluate, pipeline


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="invoice_reader")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="read, extract and check every document in a folder")
    r.add_argument("--docs", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--backend", choices=["rules", "ollama"], default="rules")
    r.add_argument("--model", default=None, help="Ollama model name (default: $INVOICE_MODEL or qwen3.5:9b)")
    r.add_argument("--resume", action="store_true", help="keep answers already read (their checks are rerun); read only the missing or failed ones")
    r.add_argument("--limit", type=int, default=None, help="read only the first N documents")
    e = sub.add_parser("eval", help="score a run against the correct answers")
    e.add_argument("--pred", required=True)
    e.add_argument("--truth", required=True)
    e.add_argument("--manifest", default=None)
    e.add_argument("--title", default=None)
    c = sub.add_parser("compare", help="one results table across runs")
    c.add_argument("runs", nargs="+", help="method|layouts|run folder, e.g. 'Rules|known|results/rules'")
    a = ap.parse_args(argv)
    if a.cmd == "compare":
        print(evaluate.compare_md([tuple(x.split("|", 2)) for x in a.runs]))
        return
    if a.cmd == "run":
        rows = pipeline.run(a.docs, a.out, a.backend, a.model, a.resume, a.limit)
        print(f"\n{len(rows)} documents: {sum(not r['issues'] for r in rows)} ready, "
              f"{sum(bool(r['issues']) for r in rows)} need review -> {a.out}/invoices.xlsx")
    else:
        res = evaluate.evaluate(a.pred, a.truth, a.manifest)
        evaluate.write(res, a.pred, a.title or f"Results: {a.pred}")
        print(evaluate.report_md(res, a.title or f"Results: {a.pred}"))


if __name__ == "__main__":
    main()
