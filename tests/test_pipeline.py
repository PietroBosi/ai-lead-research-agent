"""Tests use a fictional company ("ExampleCo") and a fake LLM: no network, no API key."""
import pytest

from leadagent import pipeline
from leadagent.config import load_icp, validate_icp
from leadagent.facts import verify_facts
from leadagent.scoring import score_lead

ICP = load_icp()

DOCS = [
    {"source_type": "website", "url": "https://example.test", "retrieved_at": "2026-01-01T00:00:00+00:00",
     "text": "ExampleCo sells outdoor gear online and in 40 stores. We employ about 400 people."},
    {"source_type": "news", "url": "https://news.test/1", "retrieved_at": "2026-01-01T00:00:00+00:00",
     "text": "ExampleCo opens new warehouse (published Mon, 01 Dec 2025)"},
]

GOOD_RAW = {
    "business_description": {"value": "Sells outdoor gear.", "evidence": "ExampleCo sells outdoor gear online"},
    "industry": {"value": "online_retail", "evidence": "sells outdoor gear online and in 40 stores"},
    "sells_physical_products": {"value": "yes", "evidence": "sells outdoor gear online"},
    "sales_channels": {"value": "online_and_stores", "evidence": "online and in 40 stores"},
    "company_size": {"value": "201-1000", "evidence": "We employ about 400 people"},
    "growth_signal": {"value": "expansion_or_launch", "evidence": "ExampleCo opens new warehouse"},
}


class FakeLLM:
    model = "fake"

    def __init__(self):
        self.calls = 0

    def generate_json(self, system, prompt):
        self.calls += 1
        if "Return a JSON object with these keys" in prompt:
            return GOOD_RAW
        return {"summary": "ExampleCo sells outdoor gear.", "subject": "Idea for ExampleCo",
                "body": "Hi [Recipient name], ..."}


def test_icp_config_is_valid():
    validate_icp(ICP)


def test_invalid_weights_rejected():
    bad = {"criteria": [{"id": "x", "weight": 50, "points": {"a": 50}}]}
    with pytest.raises(ValueError):
        validate_icp(bad)


def test_perfect_lead_scores_100():
    s = score_lead(verify_facts(GOOD_RAW, DOCS), ICP)
    assert s["score"] == 100 and s["confidence"] == 1.0 and s["tier"] == "High priority"


def test_scoring_is_deterministic():
    facts = verify_facts(GOOD_RAW, DOCS)
    assert score_lead(facts, ICP) == score_lead(facts, ICP)


def test_fabricated_evidence_becomes_unknown():
    raw = dict(GOOD_RAW, company_size={"value": "1000+", "evidence": "We employ over 5,000 people"})
    facts = verify_facts(raw, DOCS)
    assert facts["company_size"]["status"] == "unknown"
    s = score_lead(facts, ICP)
    assert s["score"] == 80 and s["confidence"] == 0.8   # lost the 20 company-size points
    assert s["max_possible"] == 100


def test_invalid_enum_value_becomes_unknown():
    raw = dict(GOOD_RAW, industry={"value": "space_mining", "evidence": "sells outdoor gear online"})
    assert verify_facts(raw, DOCS)["industry"]["status"] == "unknown"


def test_growth_none_needs_news_sources():
    raw = dict(GOOD_RAW, growth_signal={"value": "none", "evidence": ""})
    assert verify_facts(raw, DOCS)["growth_signal"]["status"] == "verified"
    assert verify_facts(raw, DOCS[:1])["growth_signal"]["status"] == "unknown"


def test_marketplace_is_capped_and_explained():
    raw = dict(GOOD_RAW, industry={"value": "online_marketplace", "evidence": "sells outdoor gear online and in 40 stores"})
    s = score_lead(verify_facts(raw, DOCS), ICP)
    assert s["score"] == 40 and s["max_possible"] == 40
    assert len(s["caps_applied"]) == 1 and "online_marketplace" in s["caps_applied"][0]


def test_decline_signal_caps_score():
    raw = dict(GOOD_RAW, growth_signal={"value": "restructuring_or_decline", "evidence": "ExampleCo opens new warehouse"})
    s = score_lead(verify_facts(raw, DOCS), ICP)
    assert s["score"] == 55 and s["tier"] == "Medium"


def test_no_email_below_outreach_threshold():
    raw = dict(GOOD_RAW, industry={"value": "online_marketplace", "evidence": "sells outdoor gear online and in 40 stores"})
    snap = {"company": "LowFitCo", "docs": DOCS, "facts_raw": raw,
            "draft": {"summary": "S.", "subject": "Hello", "body": "Hi [Recipient name]"}}
    r = pipeline.build_result(snap, ICP, "demo")
    assert r["email_body"] == "" and any("No email draft" in n for n in r["notes"])


def test_cap_on_unknown_field_rejected():
    bad = {"criteria": [{"id": "x", "field": "industry", "weight": 100, "points": {"a": 100}}],
           "caps": [{"field": "nope", "value": "a", "max_score": 10, "reason": "r"}]}
    with pytest.raises(ValueError):
        validate_icp(bad)


def test_empty_ai_output_gives_zero_score_and_low_confidence():
    s = score_lead(verify_facts({}, DOCS), ICP)
    assert s["score"] == 0 and s["low_confidence"] and s["tier"] == "Low / not a fit"


def test_live_then_demo_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "collect", lambda name, website: DOCS)
    llm = FakeLLM()
    live = pipeline.process_company("ExampleCo", "example.test", "live", ICP, llm, tmp_path)
    assert llm.calls == 2 and live["score"] == 100 and live["email_subject"] == "Idea for ExampleCo"
    demo = pipeline.process_company("ExampleCo", "example.test", "demo", ICP, None, tmp_path)
    assert demo["score"] == live["score"] and llm.calls == 2   # demo made no LLM calls


def test_live_without_sources_skips_llm(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "collect", lambda name, website: [])
    llm = FakeLLM()
    r = pipeline.process_company("GhostCo", "", "live", ICP, llm, tmp_path)
    assert llm.calls == 0 and r["score"] == 0 and r["email_body"] == ""
    assert "Not verified" in r["summary"]


def test_demo_without_snapshot_gives_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        pipeline.process_company("Nobody", "", "demo", ICP, None, tmp_path)
