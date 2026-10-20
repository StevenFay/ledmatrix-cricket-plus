"""
Country flags for national cricket sides.

ESPN tags every team with its country ("location"), including the sides that
are not the full national XI: "Australia A", "Australia Women", "Australia
Under-19s" and "England Lions" all carry their country's name. Those get the
country's flag from ``assets/country_flags`` (square flags from flag-icons,
MIT; see LICENSE-flag-icons there). Franchise and domestic teams -- Brisbane
Heat, Queensland, Barbados Royals -- keep their logos.

West Indies has no country flag, so it falls through to the bundled badge.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

FLAGS_DIR = Path(__file__).resolve().parent / "assets" / "country_flags"

#: What may follow the country's name in a national side's name. "Barbados
#: Royals" (a CPL franchise) stays a franchise; "Australia A" is a national side.
_NATIONAL_SUFFIX = re.compile(
    r"^(?:a|xi|lions|wolves|emerging|development|academy|"
    r"women(?:'s)?(?:\s+a)?|"
    r"(?:women(?:'s)?\s+)?(?:under[-\s]?\d+s?|u-?\d+s?))?$")

_index: Optional[Dict[str, str]] = None


def _countries() -> Dict[str, str]:
    global _index
    if _index is None:
        try:
            data = json.loads((FLAGS_DIR / "countries.json").read_text(encoding="utf-8"))
            _index = {k: v for k, v in data.get("countries", {}).items()}
        except (OSError, ValueError):
            _index = {}
    return _index


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def flag_code(team: Dict[str, Any]) -> Optional[str]:
    """The flag-icons code for a national side ("au", "gb-eng"), else None.

    A team is a national side when ESPN flags it ``is_national``, or when its
    name is its country plus a national-side suffix ("Australia A",
    "Australia Women"). Its country is ESPN's ``location``, else the name.
    """
    countries = _countries()
    location = _norm(team.get("location"))
    name = _norm(team.get("name"))
    if location and location in countries:
        if team.get("is_national") or name == location:
            return countries[location]
        if name.startswith(location + " ") and _NATIONAL_SUFFIX.match(name[len(location) + 1:]):
            return countries[location]
        return None
    # No usable location: a name that is itself a country is a national side.
    if name in countries:
        return countries[name]
    for country, code in countries.items():
        if name.startswith(country + " ") and _NATIONAL_SUFFIX.match(name[len(country) + 1:]):
            return code
    return None


def flag_path(team: Dict[str, Any]) -> Optional[Path]:
    code = flag_code(team)
    if not code:
        return None
    path = FLAGS_DIR / f"{code}.png"
    return path if path.exists() else None
