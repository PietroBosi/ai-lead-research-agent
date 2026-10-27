"""Step 5 - save results as CSV and as a single self-contained HTML report."""
import csv
from html import escape

CSV_COLUMNS = [
    "company", "website", "score", "tier", "confidence", "needs_review", "summary",
    "score_breakdown", "notes", "email_subject", "email_body", "sources", "mode", "collected_at",
]


def write_csv(results, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig: opens cleanly in Excel
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "company": r["company"], "website": r["website"], "score": r["score"],
                "tier": r["tier"], "confidence": r["confidence"],
                "needs_review": "yes" if r["low_confidence"] else "no", "summary": r["summary"],
                "score_breakdown": "; ".join(f'{b["label"]}: {b["points"]}/{b["weight"]}' for b in r["breakdown"]),
                "notes": " | ".join(r["notes"]),
                "email_subject": r["email_subject"], "email_body": r["email_body"],
                "sources": "; ".join(s["url"] for s in r["sources"]),
                "mode": r["mode"], "collected_at": r["collected_at"],
            })


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#1d2330;--muted:#5d6678;--line:#e1e5ec;--high:#0f7b4a;--med:#b36b00;--low:#8a94a6;--accent:#2f5bd8}
@media(prefers-color-scheme:dark){:root{--bg:#12151c;--card:#1b2029;--text:#e8ebf2;--muted:#9aa4b5;--line:#2c3340;--high:#4cc38a;--med:#e5a54b;--low:#8a94a6;--accent:#7b9bff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:920px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:24px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 20px}
.banner{border:1px solid var(--line);border-left:4px solid var(--accent);background:var(--card);padding:10px 14px;border-radius:8px;margin-bottom:20px;color:var(--muted);font-size:14px}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 16px;min-width:130px}
.stat b{display:block;font-size:22px}.stat span{color:var(--muted);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px;margin-bottom:16px}
.head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.head h2{font-size:18px;margin:0}.head a{color:var(--muted);font-size:13px}
.score{text-align:right;white-space:nowrap}.score b{font-size:28px}.score span{color:var(--muted)}
.tier{font-weight:600;font-size:13px}.tier.high{color:var(--high)}.tier.med{color:var(--med)}.tier.low{color:var(--low)}
.flag{display:inline-block;margin-left:8px;font-size:12px;border:1px solid var(--med);color:var(--med);border-radius:4px;padding:0 6px}
.bar{height:6px;background:var(--line);border-radius:3px;overflow:hidden;margin:8px 0 4px}.bar i{display:block;height:100%;background:var(--accent)}
.conf{color:var(--muted);font-size:13px}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:14px}
td,th{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:500}
td.pts{white-space:nowrap}.unk{color:var(--muted)}
details{margin-top:10px}summary{cursor:pointer;color:var(--accent);font-weight:500}
pre{white-space:pre-wrap;font:inherit;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:12px;margin:8px 0}
.note{border-left:3px solid var(--med);padding:2px 10px;margin:8px 0;color:var(--muted);font-size:13px}
.src{font-size:13px;color:var(--muted)}.src a{color:var(--muted)}
"""


def _tier_class(tier):
    return {"High priority": "high", "Medium": "med"}.get(tier, "low")


def _safe_href(url):
    return escape(url, quote=True) if url.startswith(("http://", "https://")) else "#"


def _card(r):
    rows = "".join(
        f'<tr class="{"unk" if b["status"] == "unknown" else ""}"><td>{escape(b["label"])}</td>'
        f'<td class="pts">{b["points"]}/{b["weight"]}</td><td>{escape(b["note"])}</td></tr>'
        for b in r["breakdown"]
    )
    sources = " &middot; ".join(
        f'<a href="{_safe_href(s["url"])}" rel="noopener noreferrer">{escape(s["type"])}</a>' for s in r["sources"]
    ) or "none available"
    flag = '<span class="flag">low confidence - verify manually</span>' if r["low_confidence"] else ""
    site = (f'<a href="{_safe_href(r["website"])}" rel="noopener noreferrer">{escape(r["website"])}</a>'
            if r["website"] else "")
    email = ""
    if r["email_body"]:
        email = (f'<details><summary>Email draft (not sent)</summary><pre><b>Subject:</b> '
                 f'{escape(r["email_subject"])}\n\n{escape(r["email_body"])}</pre></details>')
    return f"""
<section class="card">
  <div class="head">
    <div><h2>{escape(r["company"])}</h2>{site}</div>
    <div class="score"><b>{r["score"]}</b><span>/100</span><br>
      <span class="tier {_tier_class(r["tier"])}">{escape(r["tier"])}</span></div>
  </div>
  <div class="bar"><i style="width:{r["score"]}%"></i></div>
  <div class="conf">Confidence {int(r["confidence"] * 100)}% - could reach {r["max_possible"]} if unverified facts were confirmed {flag}</div>
  <p>{escape(r["summary"])}</p>
  {"".join(f'<div class="note">{escape(n)}</div>' for n in r["notes"])}
  <table><tr><th>Criterion</th><th>Points</th><th>Why</th></tr>{rows}</table>
  {email}
  <p class="src">Sources: {sources}</p>
</section>"""


def write_html(results, path, icp):
    ranked = sorted(results, key=lambda r: r["score"], reverse=True)
    counts = {t: sum(1 for r in ranked if r["tier"] == t) for t in ("High priority", "Medium", "Low / not a fit")}
    demo = any(r["mode"] == "demo" for r in ranked)
    banner = ("Demo mode: results are replayed from saved research snapshots. Scores are recomputed "
              "from the saved facts each run." if demo else
              "Live mode: research collected from public sources at run time.")
    stats = "".join(f'<div class="stat"><b>{n}</b><span>{escape(t)}</span></div>' for t, n in counts.items())
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Lead Research Report</title>
<style>{CSS}</style></head><body><main>
<h1>Lead Research &amp; Scoring Report</h1>
<p class="sub">Leads scored for {escape(icp["seller"]["company"])}</p>
<div class="banner">{escape(banner)} Emails are drafts and are never sent.</div>
<div class="stats">{stats}</div>
{"".join(_card(r) for r in ranked)}
</main></body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
