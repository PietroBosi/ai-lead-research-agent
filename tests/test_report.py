import csv

from leadagent import pipeline
from leadagent.report import write_csv, write_html
from test_pipeline import DOCS, ICP, FakeLLM


def _result(tmp_path, monkeypatch, name="ExampleCo <b>"):
    monkeypatch.setattr(pipeline, "collect", lambda n, w: DOCS)
    return pipeline.process_company(name, "example.test", "live", ICP, FakeLLM(), tmp_path)


def test_csv_has_one_row_per_lead(tmp_path, monkeypatch):
    r = _result(tmp_path, monkeypatch)
    write_csv([r], tmp_path / "out.csv")
    rows = list(csv.DictReader(open(tmp_path / "out.csv", encoding="utf-8-sig")))
    assert len(rows) == 1 and rows[0]["score"] == "100" and rows[0]["needs_review"] == "no"


def test_html_escapes_company_names(tmp_path, monkeypatch):
    r = _result(tmp_path, monkeypatch)
    write_html([r], tmp_path / "report.html", ICP)
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "ExampleCo &lt;b&gt;" in html and "ExampleCo <b>" not in html
    assert "never sent" in html
