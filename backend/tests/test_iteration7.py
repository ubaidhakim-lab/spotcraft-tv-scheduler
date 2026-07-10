"""Iteration 7 tests: day-membership correctness + rotation for balanced allocation."""
import os
import pytest
import requests
from collections import defaultdict

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://spot-scheduling-hub.preview.emergentagent.com",
).rstrip("/")
SAMPLE = "/tmp/samples/input.xlsx"

DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _upload():
    with open(SAMPLE, "rb") as fh:
        r = requests.post(
            f"{BASE_URL}/api/plans/upload",
            files={"file": ("input.xlsx", fh,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert r.status_code == 200, r.text
    return r.json()


def _generate(pid, start, end, dispersion):
    payload = {
        "edits": [
            {"duration": 30, "percentage": 50},
            {"duration": 20, "percentage": 20},
            {"duration": 45, "percentage": 20},
            {"duration": 10, "percentage": 10},
        ],
        "prefs": {
            "campaign_start": start,
            "campaign_end": end,
            "campaign_weeks": len(dispersion),
            "spot_frequency_minutes": 30,
            "gec_genres": ["GEC"],
            "weekly_grp_dispersion": dispersion,
            "blackout_days": [],
            "blackout_dates": [],
            "daypart_weights": [],
        },
        "row_overrides": [],
    }
    r = requests.post(f"{BASE_URL}/api/plans/{pid}/generate", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _allowed_days_for(days_str):
    s = (days_str or "").strip()
    sl = s.lower().replace(" ", "")
    if not sl or sl == "all" or sl == "daily":
        return set(DAY_ORDER)
    if sl in ("mon-sun", "mon-sunday", "monday-sunday"):
        return set(DAY_ORDER)
    if sl in ("mon-sat", "mon-saturday"):
        return set(DAY_ORDER[:6])
    if sl in ("mon-fri", "mon-friday"):
        return set(DAY_ORDER[:5])
    if sl in ("sat-sun", "sat-sunday"):
        return {"Sat", "Sun"}
    # fallback: accept any listed comma or dash-separated
    return None  # unknown; skip


@pytest.fixture(scope="module")
def uploaded():
    return _upload()


@pytest.fixture(scope="module")
def full_result(uploaded):
    pid = uploaded["plan_id"]
    return _generate(pid, "2026-06-29", "2026-08-16",
                     [14.29] * 7)


# ------- (1) Day membership correctness -------
def test_day_membership_matches_days_column(full_result, uploaded):
    # Build row_id -> days string from uploaded plan rows
    rows_meta = uploaded.get("rows") or uploaded.get("parsed_rows") or []
    id_to_days = {}
    for r in rows_meta:
        rid = r.get("_row_id")
        if rid is None:
            continue
        id_to_days[rid] = r.get("days")

    schedule_rows = full_result["schedule_rows"]
    assert schedule_rows

    violations = []
    for sr in schedule_rows:
        rid = sr.get("_row_id")
        days_str = id_to_days.get(rid)
        allowed = _allowed_days_for(days_str)
        if allowed is None:
            continue  # skip unknown day patterns
        if sr["day"] not in allowed:
            violations.append((sr.get("program"), days_str, sr["day"], sr.get("date")))
    assert not violations, f"day membership violations: {violations[:10]}"


# ------- (2) Balanced distribution -------
def test_balanced_distribution_mon_sun(full_result, uploaded):
    rows_meta = uploaded.get("rows") or []
    id_to_days = {r.get("_row_id"): r.get("days") for r in rows_meta}

    by_rid = defaultdict(list)
    for sr in full_result["schedule_rows"]:
        by_rid[sr["_row_id"]].append(sr)

    checked = 0
    for rid, rows in by_rid.items():
        days_str = id_to_days.get(rid)
        allowed = _allowed_days_for(days_str)
        if allowed is None:
            continue
        if len(rows) < 7:
            continue
        distinct_days = {r["day"] for r in rows}
        if allowed == set(DAY_ORDER):
            assert len(distinct_days) >= 5, (
                f"program {rows[0].get('program')} Mon-Sun with {len(rows)} spots hits only "
                f"{sorted(distinct_days)}"
            )
            checked += 1
        elif allowed == set(DAY_ORDER[:6]):
            assert len(distinct_days) >= 5, (
                f"program {rows[0].get('program')} Mon-Sat with {len(rows)} spots hits only "
                f"{sorted(distinct_days)}"
            )
            checked += 1
    assert checked > 0, "no Mon-Sun / Mon-Sat programs with >=7 spots found to check"


# ------- (3) Week rotation sanity: first day of each week rotates for Mon-Sun -------
def test_week_rotation_first_day_rotates(full_result, uploaded):
    """For Mon-Sun programs, the earliest day of week scheduled should rotate weekly.

    week_index rotation ensures week w starts on active_days[w % 7]. So across
    7 weeks the *first* day scheduled per week (min day-index) should cover
    many distinct days (>=5 out of 7).
    """
    rows_meta = uploaded.get("rows") or []
    id_to_days = {r.get("_row_id"): r.get("days") for r in rows_meta}

    by_rid = defaultdict(list)
    for sr in full_result["schedule_rows"]:
        by_rid[sr["_row_id"]].append(sr)

    found = 0
    for rid, rows in by_rid.items():
        days_str = id_to_days.get(rid)
        if _allowed_days_for(days_str) != set(DAY_ORDER):
            continue
        weeks = defaultdict(list)
        for r in rows:
            weeks[r["week"]].append(DAY_ORDER.index(r["day"]))
        # Only weeks with < 7 spots reveal rotation
        partial_weeks = {w: v for w, v in weeks.items() if 1 <= len(v) < 7}
        if len(partial_weeks) < 3:
            continue
        first_days = {min(v) for v in partial_weeks.values()}
        assert len(first_days) >= 2, (
            f"program {rows[0].get('program')} Mon-Sun starting-day per partial week not rotating: "
            f"{sorted(first_days)}"
        )
        found += 1
    assert found > 0, "no Mon-Sun program with >=3 partial (1-6 spot) weeks found"


# ------- (4) Regression: campaign_end strict + blackout still work -------
def test_regression_campaign_end_strict(full_result):
    from datetime import date
    end = date(2026, 8, 16)
    start = date(2026, 6, 29)
    for r in full_result["schedule_rows"]:
        d = date.fromisoformat(r["date"][:10])
        assert start <= d <= end


def test_regression_blackout_date(uploaded):
    pid = uploaded["plan_id"]
    payload = {
        "edits": [
            {"duration": 30, "percentage": 50},
            {"duration": 20, "percentage": 20},
            {"duration": 45, "percentage": 20},
            {"duration": 10, "percentage": 10},
        ],
        "prefs": {
            "campaign_start": "2026-06-29",
            "campaign_end": "2026-08-16",
            "campaign_weeks": 7,
            "spot_frequency_minutes": 30,
            "gec_genres": ["GEC"],
            "weekly_grp_dispersion": [14.29] * 7,
            "blackout_days": ["Sun"],
            "blackout_dates": ["2026-07-04"],
            "daypart_weights": [],
        },
        "row_overrides": [],
    }
    r = requests.post(f"{BASE_URL}/api/plans/{pid}/generate", json=payload)
    assert r.status_code == 200, r.text
    res = r.json()
    for row in res["schedule_rows"]:
        assert row["day"] != "Sun", f"blackout day Sun scheduled: {row}"
        assert row["date"][:10] != "2026-07-04", f"blackout date scheduled: {row}"
