"""Command line entry point: python run.py --mode demo|live"""
import argparse
import csv
import sys
import time
from pathlib import Path

from .config import ROOT, load_env, load_icp
from .llm import GeminiClient, LLMError
from .pipeline import process_company
from .report import write_csv, write_html


def read_companies(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [(row["name"].strip(), (row.get("website") or "").strip())
                for row in csv.DictReader(f) if row.get("name", "").strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(description="AI Lead Research & Scoring Agent")
    parser.add_argument("--mode", choices=["demo", "live"], default="demo",
                        help="demo = replay saved snapshots (no key); live = fresh research + Gemini")
    parser.add_argument("--input", default=str(ROOT / "data" / "input" / "companies.csv"))
    parser.add_argument("--out", default=str(ROOT / "data" / "output"))
    parser.add_argument("--company", help="run a single company name instead of the whole CSV")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows consoles default to cp1252

    load_env()
    icp = load_icp()
    companies = read_companies(args.input)
    if args.company:
        companies = [c for c in companies if c[0].lower() == args.company.lower()]
        if not companies:
            sys.exit(f"'{args.company}' is not in {args.input}")

    llm = None
    if args.mode == "live":
        try:
            llm = GeminiClient()
        except LLMError as exc:
            sys.exit(str(exc))

    results = []
    for i, (name, website) in enumerate(companies):
        print(f"[{i + 1}/{len(companies)}] {name} ({args.mode})")
        try:
            results.append(process_company(name, website, args.mode, icp, llm))
        except (FileNotFoundError, LLMError, ValueError) as exc:
            print(f"  skipped: {exc}")
        if args.mode == "live" and i < len(companies) - 1:
            time.sleep(5)   # stay under free-tier rate limits

    if not results:
        sys.exit("No results produced.")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(results, out / "results.csv")
    write_html(results, out / "report.html", icp)
    print(f"Done: {len(results)} leads -> {out / 'results.csv'} and {out / 'report.html'}")
    for r in sorted(results, key=lambda r: r["score"], reverse=True):
        print(f"  {r['score']:>3}  {r['tier']:<16} {r['company']}")


if __name__ == "__main__":
    main()
