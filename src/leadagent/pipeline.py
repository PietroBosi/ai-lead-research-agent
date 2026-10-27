"""Ties the steps together: collect -> extract facts -> verify -> score -> draft.

Two modes:
  live  - collect fresh public data and call the LLM; saves a snapshot per company.
  demo  - replay a saved snapshot (no internet, no API key). Verification and scoring
          are re-run on the snapshot, so changes to config/icp.yaml take effect.
"""
import json
import re
from pathlib import Path

from . import drafting, facts as facts_mod
from .collect import collect
from .config import ROOT
from .scoring import score_lead

SNAPSHOT_DIR = ROOT / "data" / "snapshots"
FIELD_NAMES = {
    "business_description": "business description", "industry": "industry",
    "sells_physical_products": "physical products", "sales_channels": "sales channels",
    "company_size": "company size", "growth_signal": "growth signal",
}


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def snapshot_path(name, snapshot_dir=SNAPSHOT_DIR):
    return Path(snapshot_dir) / f"{slugify(name)}.json"


def load_snapshot(name, snapshot_dir=SNAPSHOT_DIR):
    path = snapshot_path(name, snapshot_dir)
    if not path.exists():
        raise FileNotFoundError(
            f"No saved snapshot for '{name}' ({path.name}). Run in live mode once to create it."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def save_snapshot(snapshot, snapshot_dir=SNAPSHOT_DIR):
    path = snapshot_path(snapshot["company"], snapshot_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")


def build_result(snapshot, icp, mode):
    """Deterministic part: verify facts against sources, then score."""
    facts = facts_mod.verify_facts(snapshot["facts_raw"], snapshot["docs"])
    scoring = score_lead(facts, icp)
    draft = snapshot.get("draft") or {}
    outreach_ok = scoring["score"] >= icp.get("outreach_min_score", 0)
    notes = list(scoring["caps_applied"])
    if not outreach_ok:
        notes.append(f'No email draft: score is below the outreach threshold ({icp["outreach_min_score"]}).')
    missing = [FIELD_NAMES[f] for f, v in facts.items() if v["status"] != "verified"]
    summary = draft.get("summary", "No public sources could be retrieved for this company.")
    if missing:
        summary += " Not verified: " + ", ".join(missing) + "."
    return {
        "company": snapshot["company"], "website": snapshot.get("website", ""), "mode": mode,
        "collected_at": snapshot.get("collected_at", ""),
        **{k: scoring[k] for k in ("score", "max_possible", "confidence", "low_confidence", "tier", "breakdown")},
        "summary": summary,
        "email_subject": draft.get("subject", "") if outreach_ok else "",
        "email_body": draft.get("body", "") if outreach_ok else "",
        "notes": notes,
        "facts": facts,
        "sources": [{"type": d["source_type"], "url": d["url"]} for d in snapshot["docs"]],
    }


def process_company(name, website, mode, icp, llm=None, snapshot_dir=SNAPSHOT_DIR):
    if mode == "demo":
        return build_result(load_snapshot(name, snapshot_dir), icp, mode)

    docs = collect(name, website)
    snapshot = {"company": name, "website": website,
                "collected_at": max((d["retrieved_at"] for d in docs), default=""),
                "docs": docs, "facts_raw": {}, "draft": None, "model": getattr(llm, "model", "")}
    if docs:   # without any source there is nothing to extract; leave everything unknown
        snapshot["facts_raw"] = llm.generate_json(
            facts_mod.SYSTEM_PROMPT, facts_mod.build_extraction_prompt(name, docs))
        verified = facts_mod.verify_facts(snapshot["facts_raw"], docs)
        scoring = score_lead(verified, icp)
        wants_email = scoring["score"] >= icp.get("outreach_min_score", 0)   # skip email calls for poor fits
        snapshot["draft"] = drafting.validate_draft(llm.generate_json(
            drafting.SYSTEM_PROMPT, drafting.build_draft_prompt(name, verified, scoring, icp, wants_email)),
            wants_email)
    save_snapshot(snapshot, snapshot_dir)
    return build_result(snapshot, icp, mode)
