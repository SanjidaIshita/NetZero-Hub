"""Simulation of the ORG-001 solar installation process, for process mining (Part F).

It "executes" many solar requests through the same process the app implements, using the app's own catalogue
(system sizes, roofs, add-ons, installers), price rules (`price_breakdown`), 10% deposit rule and staff status
transitions (`SolarRequest.STAFF_TRANSITIONS`), with realistic random choices and waiting times. The result is an
event log in the same format `export_solar_log` produces from the live database.

Process (happy path):
    Book site assessment -> Pay deposit -> Complete site assessment -> Pay balance -> Install system
Variations the simulation produces on purpose, so there is something to discover:
    * Pay in full instead of a deposit, or pay nothing until after the assessment
    * Cancel before or after the assessment (customer), or after the assessment (installer, e.g. unsuitable roof)
    * Issue refund after every cancellation where money was paid
    * Some customers pay the balance late, AFTER installation (a deviation from the intended process)
    * Batteries add a stock delay before installation
    * South Coast Solar has one crew covering a large region (travel days on every job), so its customers wait
      longest for installation (a resource bottleneck)
"""
import random
from datetime import datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

from .catalogue import ADD_ONS, ROOF_TYPES, STOREYS, SYSTEM_SIZES, find_installer
from .models import SolarRequest, SolarRequestEvent
from .process_log import SYDNEY
from .services import deposit_amount, price_breakdown, recommend_size

A = SolarRequestEvent.Activity
S = SolarRequest.Status

# Installers we simulate: share of requests, postcodes, staff, crews and how far ahead assessments are booked.
INSTALLERS = {
    "Illawarra Solar Installs": {
        "share": 0.40, "postcodes": ["2500", "2502", "2515", "2518", "2519", "2526", "2528", "2530"],
        "assessors": ["Sam Patel", "Mia Wong"], "crews": ["Illawarra crew 1", "Illawarra crew 2", "Illawarra crew 3"],
        "lead": (1, 6), "travel_days": 0,
    },
    "Harbour City Solar": {
        "share": 0.30, "postcodes": ["2000", "2010", "2150", "2204"],
        "assessors": ["Leo Martin", "Aisha Khan", "Tom Nguyen"],
        "crews": ["Harbour crew 1", "Harbour crew 2", "Harbour crew 3"], "lead": (1, 5), "travel_days": 0,
    },
    "Hunter Solar Group": {
        "share": 0.15, "postcodes": ["2280", "2290", "2300", "2304"],
        "assessors": ["Grace Lee"], "crews": ["Hunter crew 1", "Hunter crew 2"], "lead": (2, 7), "travel_days": 0,
    },
    # Deliberately under-resourced: one assessor and one crew covering a large regional area,
    # so every job also needs travel days.
    "South Coast Solar": {
        "share": 0.15, "postcodes": ["2535", "2536", "2537", "2540", "2541"],
        "assessors": ["Ben Carter"], "crews": ["South Coast crew 1"], "lead": (3, 12), "travel_days": 1,
    },
}

# Random choices (probabilities)
ROOF_MIX = {"tiled": 0.45, "metal": 0.30, "terracotta": 0.12, "flat": 0.08, "slate": 0.05}
STOREY_MIX = {"single": 0.60, "double": 0.35, "triple": 0.05}
ADD_ON_RATES = {"battery": 0.30, "monitoring": 0.35, "ev_charger": 0.12, "bird_proofing": 0.15, "panel_cleaning": 0.08}


def _pick(rng, weights):
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def _working_day(d):
    """Assessments and installs happen Monday to Saturday."""
    return d + timedelta(days=1) if d.weekday() == 6 else d


def _at(d, hour, minute=0):
    return datetime.combine(d, time(hour, minute), tzinfo=SYDNEY)


def _hours(rng, lo, hi):
    return timedelta(hours=rng.uniform(lo, hi))


class _Case:
    def __init__(self, case_id, attrs):
        self.case_id, self.attrs, self.rows = case_id, attrs, []
        self.status, self.paid = S.CONFIRMED, Decimal("0")

    def log(self, activity, ts, resource, role, amount=""):
        self.rows.append({"case_id": self.case_id, "activity": str(activity), "timestamp": ts,
                          "resource": resource, "role": role, "amount": amount, **self.attrs})

    def move(self, new_status):
        """Status changes follow the app's own rules."""
        assert new_status in SolarRequest.STAFF_TRANSITIONS[self.status], (self.status, new_status)
        self.status = new_status

    def pay(self, activity, amount, ts):
        self.paid += amount
        self.log(activity, ts, self.attrs["customer"], "Customer", float(amount))

    def cancel(self, ts, resource, role):
        self.move(S.CANCELLED)
        self.log(A.CANCEL, ts, resource, role)
        if self.paid > 0:
            self.log(A.REFUND, ts + timedelta(seconds=1), "NetZero Hub", "System", float(self.paid))
            self.paid = Decimal("0")


def simulate(cases=500, seed=42, start="2026-01-05", end="2026-08-31"):
    """Run the solar process `cases` times. Returns a list of event-log rows."""
    rng = random.Random(seed)
    start_d = datetime.strptime(start, "%Y-%m-%d").date()
    span = (datetime.strptime(end, "%Y-%m-%d").date() - start_d).days
    names = list(INSTALLERS)
    waiting_for_install = []  # (ready time, case, installer, deposit-paid?)
    all_cases = []

    for n in range(1, cases + 1):
        # --- Customer and quote ------------------------------------------------------------
        installer = rng.choices(names, weights=[INSTALLERS[i]["share"] for i in names])[0]
        cfg = INSTALLERS[installer]
        postcode = rng.choice(cfg["postcodes"])
        assert find_installer(postcode)["name"] == installer
        usage = max(300, int(rng.lognormvariate(7.25, 0.35)))  # about 1,400 kWh a quarter on average
        size = recommend_size(usage)["id"]
        if rng.random() < 0.2:  # some people go one size up or down
            i = [s["id"] for s in SYSTEM_SIZES].index(size)
            size = SYSTEM_SIZES[max(0, min(len(SYSTEM_SIZES) - 1, i + rng.choice([-1, 1])))]["id"]
        roof, storeys = _pick(rng, ROOF_MIX), _pick(rng, STOREY_MIX)
        add_ons = [a["id"] for a in ADD_ONS if rng.random() < ADD_ON_RATES.get(a["id"], 0)]
        total = Decimal(sum(line["amount"] for line in price_breakdown(size, roof, storeys, add_ons)))
        deposit = deposit_amount(SimpleNamespace(total_price=total))
        battery = "battery" in add_ons

        booked = _at(start_d + timedelta(days=rng.randrange(span + 1)), rng.randint(7, 20), rng.randrange(60))
        case = _Case(f"ORG-001-SIM-{n:04d}", {
            "customer": f"Customer {n:04d}", "installer": installer, "postcode": postcode, "system_size": size,
            "roof_type": roof, "storeys": storeys, "battery": battery, "add_ons": "+".join(add_ons) or "none",
            "total_price": float(total),
        })
        all_cases.append(case)
        case.log(A.BOOK, booked, "NetZero Hub", "System")

        # --- Site assessment booked ahead ----------------------------------------------------
        assess_day = _working_day(booked.date() + timedelta(days=rng.randint(*cfg["lead"])))
        slot_start = rng.choice([8, 12])
        assessed_at = _at(assess_day, slot_start) + _hours(rng, 1, 3.5)
        assessor = rng.choice(cfg["assessors"])

        # --- Optional payment before the assessment -----------------------------------------
        r = rng.random()
        full_rate = 0.20 if total < 8000 else 0.08
        if r < 0.50:
            case.pay(A.PAY_DEPOSIT, deposit, min(booked + timedelta(hours=rng.expovariate(1 / 8)),
                                                 assessed_at - timedelta(hours=2)))
        elif r < 0.50 + full_rate:
            case.pay(A.PAY_FULL, total, min(booked + timedelta(hours=rng.expovariate(1 / 6)),
                                            assessed_at - timedelta(hours=2)))

        # --- Customer cancels before the assessment -------------------------------------------
        if rng.random() < (0.14 if case.paid == 0 else 0.03):
            first = max(r["timestamp"] for r in case.rows)
            case.cancel(first + (assessed_at - first) * rng.uniform(0.1, 0.9), case.attrs["customer"], "Customer")
            continue

        case.move(S.ASSESSED)
        case.log(A.ASSESS, assessed_at, assessor, "Installer staff")

        # --- Installer finds the site unsuitable ----------------------------------------------
        unsuitable = 0.04 + (0.15 if roof in ("slate", "flat") else 0) + (0.06 if storeys == "triple" else 0)
        if rng.random() < unsuitable:
            case.cancel(assessed_at + _hours(rng, 4, 48), assessor, "Installer staff")
            continue

        # --- Customer cancels after seeing the final quote --------------------------------------
        after_rate = 0.22 if case.paid == 0 else (0.05 if case.paid < total else 0.015)
        if rng.random() < after_rate:
            case.cancel(assessed_at + _hours(rng, 24, 240), case.attrs["customer"], "Customer")
            continue

        # --- Deposit is required before installation is scheduled -----------------------------
        paid_by = max(r["timestamp"] for r in case.rows)
        if case.paid == 0:
            paid_by = assessed_at + _hours(rng, 12, 144)
            if rng.random() < 0.15:
                case.pay(A.PAY_FULL, total, paid_by)
            else:
                case.pay(A.PAY_DEPOSIT, deposit, paid_by)

        ready = max(assessed_at + timedelta(days=2), paid_by)
        if battery:  # waiting for battery stock
            ready += timedelta(days=rng.uniform(4, 14))
        waiting_for_install.append((ready, case, installer, case.paid < total, deposit, total))

    # --- Installation: each installer's crews take jobs in the order they become ready ----------
    crew_free = {crew: datetime.min.replace(tzinfo=SYDNEY) for cfg in INSTALLERS.values() for crew in cfg["crews"]}
    for ready, case, installer, owes_balance, deposit, total in sorted(waiting_for_install, key=lambda w: w[0]):
        crew = min(INSTALLERS[installer]["crews"], key=lambda c: crew_free[c])
        start_day = _working_day(max(ready, crew_free[crew]).date() + timedelta(days=1))
        days = (1 + (1 if case.attrs["battery"] else 0) + (1 if case.attrs["system_size"] in ("10kw", "13kw") else 0)
                + INSTALLERS[installer]["travel_days"])
        end_day = start_day
        for _ in range(days - 1):
            end_day = _working_day(end_day + timedelta(days=1))
        installed_at = _at(end_day, rng.randint(14, 16), rng.randrange(60))
        crew_free[crew] = _at(end_day + timedelta(days=1), 7)

        if owes_balance:
            last = max(r["timestamp"] for r in case.rows)
            if rng.random() < 0.80:  # pays before install, as intended
                pay_at = max(last + timedelta(hours=1), _at(start_day, 7) - _hours(rng, 6, 96))
            else:  # pays late, after the system is installed
                pay_at = None
        case.move(S.COMPLETED)
        case.log(A.INSTALL, installed_at, crew, "Installation crew")
        if owes_balance:
            if pay_at is None:
                pay_at = installed_at + _hours(rng, 20, 24 * 14)
            case.pay(A.PAY_BALANCE, total - deposit, pay_at)

    rows = [row for case in all_cases for row in case.rows]
    for row in rows:
        row.pop("customer", None)
    return rows
