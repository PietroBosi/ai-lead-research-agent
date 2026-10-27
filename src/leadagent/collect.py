"""Step 1 - collect public information about a company. No API keys needed.

Sources (all free and public):
  - the company's own website (homepage text, only if robots.txt allows it)
  - Wikipedia's summary of the company, if a matching page exists
  - the employee count from Wikidata, or else from Wikipedia's infobox, if recorded
  - recent headlines from Google News' public RSS feed

Each source becomes a "doc": {source_type, url, retrieved_at, text}.
If a source is unavailable it is simply skipped; nothing is ever invented.
"""
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

USER_AGENT = "LeadResearchAgent/0.1 (portfolio project; contact via GitHub)"
TIMEOUT = 15
MAX_SITE_CHARS = 3000   # keep excerpts short: enough for facts, small for the repo
MAX_NEWS = 6


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class _TextExtractor(HTMLParser):
    """Collects the page title, meta description and visible text."""

    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form"}

    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta = ""
        self.chunks = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            a = dict(attrs)
            name = (a.get("name") or a.get("property") or "").lower()
            if name in ("description", "og:description") and a.get("content") and not self.meta:
                self.meta = a["content"].strip()

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title += text
        elif not self._skip_depth and len(text) > 2:
            self.chunks.append(text)


def html_to_text(html):
    parser = _TextExtractor()
    parser.feed(html)
    parts = [p for p in (parser.title, parser.meta, " ".join(parser.chunks)) if p]
    return re.sub(r"\s+", " ", " | ".join(parts)).strip()


def normalize_url(website):
    website = (website or "").strip()
    if not website:
        return ""
    return website if website.startswith(("http://", "https://")) else "https://" + website


def _allowed_by_robots(url):
    parsed = urlparse(url)
    rp = RobotFileParser()
    try:
        resp = requests.get(urljoin(url, "/robots.txt"), headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        if resp.status_code >= 400:
            return True   # no robots.txt -> allowed
        rp.parse(resp.text.splitlines())
    except requests.RequestException:
        return True
    return rp.can_fetch(USER_AGENT, url) if parsed.netloc else False


def fetch_website(website):
    url = normalize_url(website)
    if not url:
        return None
    if not _allowed_by_robots(url):
        return None
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException:
        return None
    if "charset" not in resp.headers.get("content-type", "").lower():
        resp.encoding = "utf-8"   # requests would otherwise guess latin-1 and garble quotes
    text = html_to_text(resp.text)[:MAX_SITE_CHARS]
    if len(text) < 80:   # empty shell (JavaScript-only page, bot wall, ...)
        return None
    return {"source_type": "website", "url": resp.url, "retrieved_at": _now(), "text": text}


def _tokens(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def fetch_wikipedia(company):
    """Return the Wikipedia summary only if the page title clearly matches the company."""
    try:
        r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "opensearch", "search": company, "limit": 5, "format": "json"},
            headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT,
        )
        r.raise_for_status()
        _, titles, _, urls = r.json()
    except (requests.RequestException, ValueError):
        return None
    wanted = _tokens(company)
    for title, url in zip(titles, urls):
        if not wanted <= _tokens(title):
            continue
        try:
            s = requests.get(
                "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(title.replace(" ", "_")),
                headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT,
            )
            s.raise_for_status()
            page = s.json()
            extract = page.get("extract", "")
        except (requests.RequestException, ValueError):
            continue
        if page.get("type") == "disambiguation":   # "X may refer to ..." is not company info
            continue
        if extract:
            return {"source_type": "wikipedia", "url": url, "retrieved_at": _now(), "text": extract}
    return None


def parse_employees(entity):
    """Latest 'number of employees' (Wikidata P1128) from an entity JSON, as (count, year) or None."""
    best = None
    for claim in entity.get("claims", {}).get("P1128", []):
        try:
            amount = int(float(claim["mainsnak"]["datavalue"]["value"]["amount"]))
        except (KeyError, ValueError, TypeError):
            continue
        year = ""
        for q in claim.get("qualifiers", {}).get("P585", []):   # P585 = point in time
            try:
                year = q["datavalue"]["value"]["time"][1:5]
            except (KeyError, TypeError):
                pass
        if best is None or year > best[1]:
            best = (amount, year)
    return best


def fetch_wikidata_employees(wikipedia_url):
    """Employee count from Wikidata for the company's Wikipedia page, if recorded."""
    title = unquote(wikipedia_url.rsplit("/", 1)[-1]).replace("_", " ")
    try:
        r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "prop": "pageprops", "ppprop": "wikibase_item",
                    "titles": title, "format": "json"},
            headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT,
        )
        r.raise_for_status()
        pages = r.json()["query"]["pages"]
        qid = next(iter(pages.values()))["pageprops"]["wikibase_item"]
        e = requests.get(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json",
                         headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        e.raise_for_status()
        employees = parse_employees(e.json()["entities"][qid])
    except (requests.RequestException, KeyError, ValueError, StopIteration):
        return None
    if not employees:
        return None
    count, year = employees
    when = f" (as of {year})" if year else ""
    return {"source_type": "wikidata", "url": f"https://www.wikidata.org/wiki/{qid}",
            "retrieved_at": _now(), "text": f"Number of employees: {count}{when}"}


def parse_infobox_employees(wikitext):
    """Pull the 'num_employees' value out of a Wikipedia infobox, e.g. '4,500 (2024)'."""
    m = re.search(r"\|\s*num_employees\s*=(.*?)(?=\n\s*\|\s*\w+\s*=|\n\}\}|\Z)", wikitext, flags=re.S)
    if not m:
        return None
    value = re.sub(r"<ref[^>]*/>|<ref.*?</ref>|<!--.*?-->", "", m.group(1), flags=re.S)
    # Unwrap templates, innermost first: {{circa|900}} -> 900, {{list|542 (2024)|927 (2023)}} -> 542 (2024); 927 (2023)
    # Templates without digits ({{Decrease}}) are dropped.
    def unwrap(t):
        parts = [re.sub(r"^\w+:", "", p).strip() for p in t.group(1).split("|")]
        if not re.search(r"\d", parts[0]):
            parts = parts[1:]
        return "; ".join(p for p in parts if p)

    for _ in range(5):
        value, n = re.subn(r"\{\{([^{}]*)\}\}", unwrap, value)
        if not n:
            break
    value = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", value)   # [[a|b]] -> b
    value = re.sub(r"\s+", " ", value).strip(" ,;")
    return value[:80] if re.search(r"\d", value) else None


def fetch_infobox_employees(wikipedia_url):
    title = unquote(wikipedia_url.rsplit("/", 1)[-1]).replace("_", " ")
    try:
        r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "parse", "page": title, "prop": "wikitext", "section": 0,
                    "format": "json", "redirects": 1},
            headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT,
        )
        r.raise_for_status()
        value = parse_infobox_employees(r.json()["parse"]["wikitext"]["*"])
    except (requests.RequestException, KeyError, ValueError):
        return None
    if not value:
        return None
    return {"source_type": "wikipedia_infobox", "url": wikipedia_url, "retrieved_at": _now(),
            "text": f"Number of employees: {value}"}


def fetch_news(company):
    """Latest headlines (title + date + publisher) from Google News RSS, last 12 months."""
    query = f'"{company}" when:365d'
    try:
        r = requests.get(
            "https://news.google.com/rss/search",
            params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
            headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT,
        )
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except (requests.RequestException, ET.ParseError):
        return []
    docs = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        date = (item.findtext("pubDate") or "").strip()
        if not title or not link:
            continue
        if company.lower().split()[0] not in title.lower():
            continue   # drop headlines that do not mention the company
        docs.append({
            "source_type": "news", "url": link, "retrieved_at": _now(),
            "text": f"{title} (published {date})",
        })
        if len(docs) == MAX_NEWS:
            break
    return docs


def collect(company, website=""):
    """Gather all available docs. Returns a list (possibly empty)."""
    docs = []
    site, wiki = fetch_website(website), fetch_wikipedia(company)
    docs.extend(d for d in (site, wiki) if d)
    if wiki:
        employees = fetch_wikidata_employees(wiki["url"]) or fetch_infobox_employees(wiki["url"])
        if employees:
            docs.append(employees)
    docs.extend(fetch_news(company))
    return docs
