from leadagent.collect import html_to_text, normalize_url, parse_employees


def _claim(amount, year=None):
    c = {"mainsnak": {"datavalue": {"value": {"amount": amount}}}}
    if year:
        c["qualifiers"] = {"P585": [{"datavalue": {"value": {"time": f"+{year}-01-01T00:00:00Z"}}}]}
    return c


def test_parse_employees_picks_latest_year():
    entity = {"claims": {"P1128": [_claim("+900", "2021"), _claim("+1500", "2024"), _claim("+1200", "2022")]}}
    assert parse_employees(entity) == (1500, "2024")


def test_parse_infobox_employees_cleans_markup():
    from leadagent.collect import parse_infobox_employees
    wt = "{{Infobox company\n| name = X\n| num_employees = {{increase}} 2,500 (2024)<ref>cite</ref>\n| website = x.com\n}}"
    assert parse_infobox_employees(wt) == "2,500 (2024)"
    assert parse_infobox_employees("| name = X") is None
    nested = "| num_employees    = {{Unbulleted list|{{Decrease}} 542 (2024)|927 (2023)}}\n| parent = \n"
    assert parse_infobox_employees(nested) == "542 (2024); 927 (2023)"


def test_parse_employees_missing_returns_none():
    assert parse_employees({"claims": {}}) is None


def test_html_to_text_skips_scripts_and_keeps_meta():
    html = ("<html><head><title>Acme</title><meta name='description' content='Acme sells widgets'>"
            "<script>var secret=1;</script></head><body><nav>Menu</nav><p>We make widgets for everyone.</p></body></html>")
    text = html_to_text(html)
    assert "Acme sells widgets" in text and "We make widgets" in text
    assert "secret" not in text and "Menu" not in text


def test_normalize_url():
    assert normalize_url("example.com") == "https://example.com"
    assert normalize_url("") == ""
