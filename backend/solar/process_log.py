"""Event logs for process mining (Part F): one row per activity, written as CSV (for Disco) and XES.

Every row has the three columns process mining needs, plus extra attributes for filtering:
  case_id    the solar request reference (one case = one request)
  activity   what happened, e.g. "Pay deposit"
  timestamp  when it happened (local Sydney time)
  resource   who did it (customer, staff member, installation crew or "NetZero Hub" for the system)
  role       Customer / Installer staff / Installation crew / System
"""
import csv
import re
from datetime import datetime
from xml.sax.saxutils import escape, quoteattr
from zoneinfo import ZoneInfo

SYDNEY = ZoneInfo("Australia/Sydney")

COLUMNS = [
    "case_id", "activity", "timestamp", "resource", "role",
    "installer", "postcode", "system_size", "roof_type", "storeys", "battery", "add_ons",
    "total_price", "amount",
]


def _fmt(ts):
    """Timestamps as 2026-03-04 09:15:00 (Disco reads this pattern automatically)."""
    return ts.astimezone(SYDNEY).strftime("%Y-%m-%d %H:%M:%S") if ts.tzinfo else ts.strftime("%Y-%m-%d %H:%M:%S")


def sort_rows(rows):
    return sorted(rows, key=lambda r: (r["case_id"], r["timestamp"]))


def write_csv(rows, path):
    rows = sort_rows(rows)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({**r, "timestamp": _fmt(r["timestamp"])})
    return len(rows)


def write_xes(rows, path):
    """A minimal IEEE XES file: one <trace> per case, one <event> per row."""
    rows = sort_rows(rows)
    case_attrs = ["installer", "postcode", "system_size", "roof_type", "storeys", "battery", "add_ons", "total_price"]

    def attr(key, value):
        if isinstance(value, bool):
            return f'<boolean key={quoteattr(key)} value="{str(value).lower()}"/>'
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f'<float key={quoteattr(key)} value="{value}"/>'
        return f'<string key={quoteattr(key)} value={quoteattr(str(value))}/>'

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<log xes.version="1.0" xes.features="nested-attributes" xmlns="http://www.xes-standard.org/">',
        '  <extension name="Concept" prefix="concept" uri="http://www.xes-standard.org/concept.xesext"/>',
        '  <extension name="Time" prefix="time" uri="http://www.xes-standard.org/time.xesext"/>',
        '  <extension name="Organizational" prefix="org" uri="http://www.xes-standard.org/org.xesext"/>',
        '  <string key="concept:name" value="ORG-001 Solar panel installation"/>',
    ]
    current = None
    for r in rows:
        if r["case_id"] != current:
            if current is not None:
                out.append("  </trace>")
            current = r["case_id"]
            out.append("  <trace>")
            out.append(f'    <string key="concept:name" value={quoteattr(current)}/>')
            out.extend("    " + attr(k, r.get(k, "")) for k in case_attrs)
        ts = r["timestamp"] if r["timestamp"].tzinfo else r["timestamp"].replace(tzinfo=SYDNEY)
        out.append("    <event>")
        out.append(f'      <string key="concept:name" value={quoteattr(r["activity"])}/>')
        out.append(f'      <date key="time:timestamp" value="{ts.astimezone(SYDNEY).isoformat(timespec="milliseconds")}"/>')
        out.append(f'      <string key="org:resource" value={quoteattr(r["resource"])}/>')
        out.append(f'      <string key="org:role" value={quoteattr(r["role"])}/>')
        if r.get("amount") not in (None, ""):
            out.append(f'      <float key="amount" value="{r["amount"]}"/>')
        out.append("    </event>")
    if current is not None:
        out.append("  </trace>")
    out.append("</log>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return len(rows)


# --------------------------------------------------------------------------------------------
# Real data: the events the running app has recorded
# --------------------------------------------------------------------------------------------
_AMOUNT = re.compile(r"\$([\d,]+\.\d{2})")


def rows_from_database(queryset=None):
    """Turn recorded SolarRequestEvents into event-log rows."""
    from .models import SolarRequestEvent

    qs = queryset if queryset is not None else SolarRequestEvent.objects.all()
    rows = []
    for ev in qs.select_related("request").order_by("request__reference", "created_at", "id"):
        req = ev.request
        if ev.actor == "NetZero Hub":
            role = "System"
        elif ev.actor == req.customer_name:
            role = "Customer"
        else:
            role = "Installer staff"
        m = _AMOUNT.search(ev.note or "")
        rows.append({
            "case_id": req.reference,
            "activity": ev.activity or ev.get_status_display(),
            "timestamp": ev.created_at,
            "resource": ev.actor,
            "role": role,
            "installer": req.installer,
            "postcode": req.postcode,
            "system_size": req.system_size,
            "roof_type": req.roof_type,
            "storeys": req.storeys,
            "battery": "battery" in (req.add_ons or []),
            "add_ons": "+".join(req.add_ons or []) or "none",
            "total_price": float(req.total_price),
            "amount": float(m.group(1).replace(",", "")) if m else "",
        })
    return rows


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()
