"""iso8601.py — stdlib-only UTC-safe date helpers for headless coaching briefs.

Why this exists in a plugins tree: headless cron prompts (Morgonbrief Millberg,
Morgonbrief Wilma, Veckoplan Wilma) hard-require "ALLTID datum + veckodag
tillsammans" and demand mechanical — never mental — weekday derivation, but ship
only a bare template ``python3 -c "import datetime as d; print({...}[d.date(ÅÅÅÅ,M,D).weekday()])"``
with placeholder year/month/day fields. Every agent must re-assemble that
one-liner by hand and substitute ÅÅÅÅ/M/D correctly; a wrong year or swapped
arguments fails silently and burns athlete trust. This module is the drop-in
replacement the prompts can reference instead.

Design constraints (loop contract + PR #124 precedent):
- Python 3 stdlib only — no PyYAML, no third-party deps (runs under the system
  python3; the /opt/hermes venv has yaml but the system python does not).
- Read-only against /opt/data; no network calls; no os/subprocess/eval/exec.
- Safe to import from any workdir.

Wire format note: intervals.icu ISO-8601 strings are UTC ("2026-10-01T04:21:24").
Fromisoformat returns a NAIVE datetime — it carries no tzinfo — so naive-local
arithmetic on UTC timestamps drifts by +1/+2h for Swedish athletes. These
helpers enforce: parse as UTC, keep everything in UTC, convert ONLY at the
explicit formatting boundary.
"""

import datetime as _dt
import re

_UTC = _dt.timezone.utc

# Thresholds (weeks) at which a naive/aware arithmetic bug becomes likely.
_WEEKDAY_SV = {
    0: "måndag",
    1: "tisdag",
    2: "onsdag",
    3: "torsdag",
    4: "fredag",
    5: "lördag",
    6: "söndag",
}

# Accepts: "2026-10-01", "2026-10-01T04:21:24", "...24.000000",
# "...24Z", "...24+00:00", "...24.000000Z" — plus true offsets (“+02:00”).
_ISO_TS = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?"
    r"(Z|[+-]\d{2}:?\d{2})?)?$"
)


def parse_utc(s):
    """Parse an ISO-8601 date or timestamp into an aware-UTC datetime.

    - date-only strings ("2026-10-01") -> midnight UTC that date
    - naive timestamps ("2026-10-01T04:21:24") -> ASSUMED UTC (matches the
      intervals.icu wire format); do not pass local-clock strings here
    - aware timestamps -> normalized to UTC regardless of source offset
    Raises ValueError on anything else (no silent date rollover).
    """
    if not isinstance(s, str):
        raise ValueError("iso8601.parse_utc expects a str, got %r" % type(s))
    m = _ISO_TS.match(s.strip())
    if not m:
        raise ValueError("not an ISO-8601 date/timestamp: %r" % s)
    y, mo, dd, hh, mi, ss, off = m.groups()
    dt = _dt.datetime(
        int(y), int(mo), int(dd),
        int(hh or 0), int(mi or 0), int(ss or 0),
        tzinfo=_dt.timezone.utc,
    )
    if off and off != "Z":
        sign = 1 if off[0] == "+" else -1
        off = off[1:].replace(":", "")
        delta = _dt.timedelta(hours=int(off[:2]), minutes=int(off[2:]))
        dt = (dt - sign * delta).astimezone(_UTC)
    return dt


def weekday_sv(value):
    """Swedish weekday name for an ISO date/timestamp string, YYYY-MM-DD,
    date, or datetime. Mechanically derived — never by the model."""
    if isinstance(value, str):
        dt = parse_utc(value)
    elif isinstance(value, _dt.datetime):
        dt = value
        if dt.tzinfo is None:
            raise ValueError(
                "naive datetime passed to weekday_sv — assume an explicit "
                "timezone first; naive arithmetic on UTC stamps drifts"
            )
    elif isinstance(value, _dt.date):
        dt = _dt.datetime(value.year, value.month, value.day, tzinfo=_UTC)
    else:
        raise ValueError("unsupported type for weekday_sv: %r" % type(value))
    return _WEEKDAY_SV[dt.weekday()]


def date_sv(value):
    """'2026-10-01' -> '2026-10-01 (torsdag)'. Single source of truth for the
    datum+veckodag pairing the brief prompts mandate."""
    if isinstance(value, str):
        m = _ISO_TS.match(value.strip())
        if not m:
            raise ValueError("not an ISO-8601 date/timestamp: %r" % value)
        dt = parse_utc(value)
        return "%04d-%02d-%02d (%s)" % (dt.year, dt.month, dt.day, _WEEKDAY_SV[dt.weekday()])
    if isinstance(value, _dt.date):
        return "%s (%s)" % (value.isoformat(), _WEEKDAY_SV[value.weekday()])
    raise ValueError("iso8601.date_sv expects a str or date, got %r" % type(value))
