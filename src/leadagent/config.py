"""Loading and validating configuration (ICP rules and .env settings)."""
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ICP_PATH = ROOT / "config" / "icp.yaml"


def load_env(path=None):
    """Read KEY=VALUE lines from .env into os.environ (existing variables win)."""
    path = Path(path) if path else ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_icp(path=None):
    icp = yaml.safe_load(Path(path or ICP_PATH).read_text(encoding="utf-8"))
    validate_icp(icp)
    return icp


def validate_icp(icp):
    """Fail early with a clear message if the scoring rules are inconsistent."""
    criteria = icp["criteria"]
    total = sum(c["weight"] for c in criteria)
    if total != 100:
        raise ValueError(f"Criteria weights must add up to 100, got {total}")
    known_fields = {c["field"] for c in criteria}
    for cap in icp.get("caps", []):
        if cap["field"] not in known_fields:
            raise ValueError(f"Cap refers to unknown field '{cap['field']}'")
    for c in criteria:
        too_high = {k: v for k, v in c["points"].items() if v > c["weight"]}
        if too_high:
            raise ValueError(f"'{c['id']}': points above weight {c['weight']}: {too_high}")
