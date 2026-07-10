"""Iteration 11 acceptance tests:
1. Strict day-of-week adherence
2. No 2 spots in same (row_id, date, time) slot
3. Movies genre uses hourly boundaries
4. Weekend boost slider effect
5. Reach vs frequency slider effect
6. GEC even spread across days
"""
import os
import io
import datetime as dt
from collections import Counter, defaultdict

import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://spot-scheduling-hub.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

SAMPLE = "/tmp/samples/input.xlsx"

DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def parse_days_allowed(days_str):
    """Replicate backend parse_days logic: returns allowed day set from a Days column like 'Mon-Fri'."""
    if not days_str:
        return set(DAY_ORDER)
    s = str(days_str).strip()
    aliases = {
        "mon": "Mon", "monday": "Mon",
        "tue": "Tue", "tues": "Tue", "tuesday": "Tue",
        "wed": "Wed", "wednesday": "Wed",
        "thu": "Thu", "thur": "Thu", "thurs": "Thu", "thursday": "Thu",
        "fri": "Fri", "friday": "Fri",
        "sat": "Sat", "saturday": "Sat",
        "sun": "Sun", "sunday": "Sun",
    }
    def norm(x):
        return aliases.get(x.strip().lower(), x.strip().title()[:3])
    if "-" in s:
        parts = s.split("-")
        a, b = norm(parts[0]), norm(parts[1])
        if a in DAY_ORDER and b in DAY_ORDER:
            i, j = DAY_ORDER.index(a), DAY_ORDER.index(b)
            if i <= j:
                return set(DAY_ORDER[i:j+1])
            return set(DAY_ORDER[i:] + DAY_ORDER[:j+1])
    # Comma-separated
    if "," in s:
        return {norm(x) for x in s.split(",") if norm(x) in DAY_ORDER}
    n = norm(s)
    if n in DAY_ORDER:
        return {n}
    return set(DAY_ORDER)


@pytest.fixture(scope="module")
def uploaded_plan():
    with open(SAMPLE, "rb") as f:
        files = {"file": ("input.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/plans/upload", files=files, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "plan_id" in data
    return data


def build_gen_payload(plan, **prefs_over):
    prefs = {
        "campaign_start": "2026-06-29",
        "campaign_end": "2026-08-16",
        "campaign_weeks": 7,
        "spot_frequency_minutes": 30,
        "movies_frequency_minutes": 60,
        "movies_genres": ["MOV", "Movies", "Movie"],
        "gec_genres": ["GEC"],
        "weekly_grp_dispersion": [],
        "blackout_days": [],
        "blackout_dates": [],
        "daypart_weights": [],
        "weekend_boost": 1.0,
        "reach_vs_frequency": 0.5,
    }
    prefs.update(prefs_over)
    edits = plan.get("default_edits") or [
        {"duration": 10, "percentage": 60},
        {"duration": 20, "percentage": 30},
        {"duration": 30, "percentage": 10},
    ]
    return {"edits": edits, "row_overrides": [], "prefs": prefs}


def generate(plan, **prefs_over):
    payload = build_gen_payload(plan, **prefs_over)
    r = requests.post(f"{API}/plans/{plan['plan_id']}/generate", json=payload, timeout=120)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def default_result(uploaded_plan):
    return generate(uploaded_plan)


def rows_by_rowid(plan):
    """Map raw input _row_id -> row dict (with days, genre, program, channel)."""
    m = {}
    for r in plan.get("rows", []):
        rid = r.get("_row_id")
        if rid is None:
            continue
        m[rid] = r
    return m


# ---------- Test 1: Strict day-of-week ----------
class TestStrictDay:
    def test_all_schedule_rows_respect_days(self, uploaded_plan, default_result):
        rows_map = rows_by_rowid(uploaded_plan)
        violations = []
        for sr in default_result["schedule_rows"]:
            rid = sr["_row_id"]
            raw = rows_map.get(rid, {})
            allowed = parse_days_allowed(raw.get("days"))
            d = dt.date.fromisoformat(sr["date"])
            dow = DAY_ORDER[d.weekday()]
            if dow not in allowed:
                violations.append((rid, raw.get("days"), sr["date"], dow))
        assert not violations, f"{len(violations)} day violations, first 5: {violations[:5]}"


# ---------- Test 2: No slot duplicates ----------
class TestNoSlotDupes:
    def test_no_duplicate_slots_per_rowid(self, default_result):
        counts = Counter()
        for sr in default_result["schedule_rows"]:
            counts[(sr["_row_id"], sr["date"], sr["spot_time"])] += 1
        dupes = [k for k, v in counts.items() if v > 1]
        assert not dupes, f"{len(dupes)} duplicate slots, first 5: {dupes[:5]}"

    def test_no_duplicate_slots_per_program_timeband(self, uploaded_plan, default_result):
        # For each (channel, program, start_time, end_time), each (date, time) must be unique
        rows_map = rows_by_rowid(uploaded_plan)
        occ = defaultdict(Counter)
        for sr in default_result["schedule_rows"]:
            raw = rows_map.get(sr["_row_id"], {})
            key = (sr["channel"], sr["program"], raw.get("start_time"), raw.get("end_time"))
            occ[key][(sr["date"], sr["spot_time"])] += 1
        offenders = []
        for k, c in occ.items():
            for slot, n in c.items():
                if n > 1:
                    offenders.append((k, slot, n))
        assert not offenders, f"{len(offenders)} program-timeband dupes, first 5: {offenders[:5]}"


# ---------- Test 3: Movies hourly ----------
class TestMoviesFrequency:
    def test_movie_rows_are_hourly(self, default_result):
        offenders = []
        movie_rows = 0
        for sr in default_result["schedule_rows"]:
            genre = str(sr.get("genre") or "")
            if "mov" in genre.lower():
                movie_rows += 1
                mm = sr["spot_time"].split(":")[1]
                if mm != "00":
                    offenders.append((sr.get("channel"), sr.get("program"), sr["spot_time"]))
        assert movie_rows > 0, "No movie rows found in default sample - can't validate"
        assert not offenders, f"{len(offenders)} non-hourly movie spots, first 5: {offenders[:5]}"


# ---------- Test 4: Weekend boost ----------
class TestWeekendBoost:
    def test_high_boost_yields_more_weekend_spots(self, uploaded_plan):
        high = generate(uploaded_plan, weekend_boost=2.0)
        low = generate(uploaded_plan, weekend_boost=0.5)

        def weekend_count(res):
            n = 0
            for sr in res["schedule_rows"]:
                d = dt.date.fromisoformat(sr["date"])
                if d.weekday() >= 5:  # Sat/Sun
                    n += 1
            return n

        hi_n, lo_n = weekend_count(high), weekend_count(low)
        print(f"weekend spots: high={hi_n} low={lo_n}")
        assert hi_n > lo_n, f"expected more weekend spots with boost 2.0 vs 0.5 (got {hi_n} vs {lo_n})"


# ---------- Test 5: Reach vs Frequency ----------
class TestReachVsFrequency:
    def test_reach_touches_more_days(self, uploaded_plan):
        reach = generate(uploaded_plan, reach_vs_frequency=0.0)
        freq = generate(uploaded_plan, reach_vs_frequency=1.0)

        def distinct_day_pairs(res):
            s = set()
            for sr in res["schedule_rows"]:
                s.add((sr["_row_id"], sr["date"]))
            return len(s)

        r_pairs = distinct_day_pairs(reach)
        f_pairs = distinct_day_pairs(freq)
        print(f"distinct (rowid, date) pairs: reach={r_pairs} freq={f_pairs}")
        assert r_pairs >= f_pairs, f"reach should touch >= days ({r_pairs} vs {f_pairs})"


# ---------- Test 6: GEC even spread ----------
class TestGECSpread:
    def test_gec_programs_spread_across_days(self, uploaded_plan, default_result):
        rows_map = rows_by_rowid(uploaded_plan)
        # Group schedule rows by _row_id; only consider GEC + Mon-Sun rows with >= 7 spots
        by_rid = defaultdict(list)
        for sr in default_result["schedule_rows"]:
            by_rid[sr["_row_id"]].append(sr)

        gec_checked = 0
        offenders = []
        for rid, sched in by_rid.items():
            raw = rows_map.get(rid, {})
            genre = str(raw.get("genre") or "")
            days = str(raw.get("days") or "")
            allowed = parse_days_allowed(days)
            if "gec" not in genre.lower():
                continue
            if len(allowed) < 7:
                continue
            if len(sched) < 7:
                continue
            gec_checked += 1
            dows = {DAY_ORDER[dt.date.fromisoformat(s["date"]).weekday()] for s in sched}
            if len(dows) < 5:
                offenders.append((rid, raw.get("program"), len(sched), sorted(dows)))
        print(f"GEC Mon-Sun programs with >=7 spots checked: {gec_checked}")
        if gec_checked == 0:
            pytest.skip("No GEC Mon-Sun programs with >=7 spots in sample")
        assert not offenders, f"{len(offenders)} under-spread GEC programs, first 5: {offenders[:5]}"


# ---------- Regression basics ----------
class TestRegression:
    def test_schedule_nonempty(self, default_result):
        assert len(default_result["schedule_rows"]) > 0
        assert default_result.get("result_id") or default_result.get("id")

    def test_download(self, default_result):
        rid = default_result.get("result_id") or default_result.get("id")
        r = requests.get(f"{API}/results/{rid}/download", timeout=60)
        assert r.status_code == 200
        assert len(r.content) > 1000
        assert r.headers.get("content-type", "").startswith("application/vnd.openxmlformats") or r.content[:2] == b"PK"
