import argparse
import datetime as dt
import json
import shutil
from pathlib import Path

from . import llm
from .docs import load_pack
from .pipeline import run_pipeline, run_single_shot, sources_section


def main():
    ap = argparse.ArgumentParser(description="One-page research brief agent")
    ap.add_argument("--ticker", default="SRVCABLE")
    ap.add_argument("--pack", default="data/research_pack")
    ap.add_argument("--prompts", default="prompts")
    ap.add_argument("--mode", choices=["pipeline", "single"], default="pipeline")
    ap.add_argument("--note", default="", help="what you changed since the last run (goes in the run log)")
    a = ap.parse_args()

    docs = load_pack(a.pack)
    if not docs:
        raise SystemExit(f"No documents found in {a.pack}")
    print(f"Loaded {len(docs)} docs; provider={llm.provider()} model={llm.model_name()} mode={a.mode}")
    for d in docs:
        print("  ", d.label())

    trace = {"log": []}
    brief = (run_pipeline if a.mode == "pipeline" else run_single_shot)(docs, a.ticker, a.prompts, trace)
    final = f"{brief.strip()}\n\n{sources_section(brief, docs)}\n"

    run_dir = Path("runs") / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "brief.md").write_text(final, encoding="utf-8")
    (run_dir / "trace.json").write_text(json.dumps(trace, ensure_ascii=False, indent=1), encoding="utf-8")
    (run_dir / "meta.json").write_text(json.dumps({
        "mode": a.mode, "provider": llm.provider(), "model": llm.model_name(),
        "note": a.note, "words": len(final.split())}, indent=1), encoding="utf-8")
    shutil.copytree(a.prompts, run_dir / "prompts_used")  # exact prompts for this run, for the test log

    print("\n" + "=" * 70 + "\n" + final)
    print(f"[saved to {run_dir}]  words={len(final.split())}")
    for line in trace["log"]:
        print("  note:", line)


if __name__ == "__main__":
    main()
