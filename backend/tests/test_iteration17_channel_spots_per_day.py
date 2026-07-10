"""Iteration 17 backend tests.

Covers new feature: `channel_spots_per_day` in SchedulingPrefs.
Verifies:
 1. Per-channel spots/day rate is respected (Star Plus 280/10=28 days; Sony Max 60/5=12 days).
 2. Channels without an entry use full campaign window.
 3. No-drop invariant still holds when channel_spots_per_day is set.
 4. Empty list behaves like the previous (unconstrained) behaviour.
 5. Very low spots_per_day (over-cap) still schedules all spots via stacking.
 6. Interaction with gec_planning_weeks -- stricter (smaller) of the two wins.
"""
import io
import os
from collections import Counter
from datetime import datetime, timedelta

import pytest
import requests
from openpyxl import Workbook

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

STANDARD_HEADERS = [
    "Market", "Genre", "Channel", "Program", "Days", "Start Time", "End Time",
    "Net Rate 10Sec", "ACD", "Spots", "FCT", "Net Outlay", "Log TVR", "GRP",
]


def build_plan_xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "Plan"
    ws.append(["Client", "TEST"])
    ws.append(["Campaign", "ITER17"])
    ws.append([])
    ws.append(STANDARD_HEADERS)
    for r in rows:
        ws.append([r.get(h, "") for h in STANDARD_HEADERS])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def upload_plan(rows):
    buf = build_plan_xlsx(rows)
    resp = requests.post(
        f"{API}/plans/upload",
        files={"file": ("plan.xlsx", buf,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        timeout=30,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def generate(plan_id, edits, prefs, row_overrides=None):
    body = {"edits": edits, "row_overrides": row_overrides or [], "prefs": prefs}
    resp = requests.post(f"{API}/plans/{plan_id}/generate", json=body, timeout=60)
    assert resp.status_code == 200, resp.text
    return resp.json()


def invariant(gen):
    er = gen["edit_rows"]
    sr = gen["schedule_rows"]
    total_final = sum(e["final_spots"] for e in er)
    assert len(sr) == total_final, f"MISMATCH sched={len(sr)} vs final={total_final}"


# ---------- Tests ----------

class TestChannelSpotsPerDay:

    def test_star_plus_280_at_10_per_day_yields_about_28_days(self):
        rows = [{
            "Market": "HIN", "Genre": "GEC", "Channel": "Star Plus",
            "Program": "Prime Time", "Days": "Mon-Sun",
            "Start Time": "19:00", "End Time": "23:00",
            "Net Rate 10Sec": 5000, "ACD": 10, "Spots": 280, "FCT": 2800,
        }]
        d = upload_plan(rows)
        gen = generate(d["plan_id"],
                       edits=[{"duration": 10, "percentage": 100}],
                       prefs={
                           "campaign_start": "2026-01-05",
                           "campaign_end": "2026-03-01",  # ~8 weeks -> full window would spread over 56 days
                           "channel_spots_per_day": [{"channel": "Star Plus", "spots_per_day": 10}],
                       })
        invariant(gen)
        sr = gen["schedule_rows"]
        assert len(sr) == 280
        per_day = Counter(s["date"] for s in sr)
        n_days = len(per_day)
        # eff_weeks = ceil(280/10/7) = 4 weeks = 28 days -> aired across 28 days (Mon-Sun)
        assert 25 <= n_days <= 30, f"expected ~28 active days, got {n_days}"
        # Approximate rate
        mean_per_day = 280 / n_days
        assert 9.0 <= mean_per_day <= 11.5, f"mean/day={mean_per_day:.2f}"

    def test_sony_max_60_at_5_per_day_yields_about_12_14_days(self):
        rows = [{
            "Market": "HIN", "Genre": "Movies", "Channel": "Sony Max",
            "Program": "Movie Block", "Days": "Mon-Sun",
            "Start Time": "20:00", "End Time": "23:00",
            "Net Rate 10Sec": 3000, "ACD": 10, "Spots": 60, "FCT": 600,
        }]
        d = upload_plan(rows)
        gen = generate(d["plan_id"],
                       edits=[{"duration": 10, "percentage": 100}],
                       prefs={
                           "campaign_start": "2026-01-05",
                           "campaign_end": "2026-03-01",
                           "movies_frequency_minutes": 30,
                           "channel_spots_per_day": [{"channel": "Sony Max", "spots_per_day": 5}],
                       })
        invariant(gen)
        sr = gen["schedule_rows"]
        assert len(sr) == 60
        n_days = len(Counter(s["date"] for s in sr))
        # ceil(60/5)=12 days -> ceil(12/7)=2 weeks -> up to 14 days
        assert 10 <= n_days <= 14, f"expected 10..14 days, got {n_days}"

    def test_channel_without_entry_uses_full_window(self):
        rows = [
            {"Market": "HIN", "Genre": "GEC", "Channel": "Star Plus", "Program": "P1",
             "Days": "Mon-Sun", "Start Time": "19:00", "End Time": "23:00",
             "Net Rate 10Sec": 5000, "ACD": 10, "Spots": 100, "FCT": 1000},
            {"Market": "HIN", "Genre": "News", "Channel": "Aaj Tak", "Program": "News Hr",
             "Days": "Mon-Sun", "Start Time": "20:00", "End Time": "22:00",
             "Net Rate 10Sec": 2000, "ACD": 10, "Spots": 42, "FCT": 420},
        ]
        d = upload_plan(rows)
        gen = generate(d["plan_id"],
                       edits=[{"duration": 10, "percentage": 100}],
                       prefs={
                           "campaign_start": "2026-01-05",
                           "campaign_end": "2026-02-15",  # 6 weeks = 42 days
                           "channel_spots_per_day": [{"channel": "Star Plus", "spots_per_day": 10}],
                       })
        invariant(gen)
        sr = gen["schedule_rows"]
        aaj_days = len(Counter(s["date"] for s in sr if s["channel"] == "Aaj Tak"))
        # Aaj Tak (42 spots, no cap) should spread across full 42-day window
        assert aaj_days >= 30, f"Aaj Tak spread only {aaj_days} days (expected full window ~42)"

    def test_empty_channel_spots_per_day_matches_previous_behavior(self):
        rows = [{
            "Market": "HIN", "Genre": "GEC", "Channel": "CH1", "Program": "P1",
            "Days": "Mon-Fri", "Start Time": "20:00", "End Time": "22:00",
            "Net Rate 10Sec": 1000, "ACD": 20, "Spots": 60, "FCT": 1200,
        }]
        d = upload_plan(rows)
        prefs_base = {"campaign_start": "2026-01-05", "campaign_end": "2026-01-18"}
        gen1 = generate(d["plan_id"],
                        edits=[{"duration": 20, "percentage": 100}],
                        prefs=prefs_base)
        gen2 = generate(d["plan_id"],
                        edits=[{"duration": 20, "percentage": 100}],
                        prefs={**prefs_base, "channel_spots_per_day": []})
        invariant(gen1)
        invariant(gen2)
        assert len(gen1["schedule_rows"]) == len(gen2["schedule_rows"]) == 60

    def test_very_low_rate_stacks_but_never_drops(self):
        """500 spots, cap 1/day * 14 days = 14 slots... backend must stack, not drop."""
        rows = [{
            "Market": "HIN", "Genre": "GEC", "Channel": "GECbig", "Program": "Prime",
            "Days": "Mon-Sun", "Start Time": "20:00", "End Time": "22:00",
            "Net Rate 10Sec": 5000, "ACD": 10, "Spots": 500, "FCT": 5000,
        }]
        d = upload_plan(rows)
        gen = generate(d["plan_id"],
                       edits=[{"duration": 10, "percentage": 100}],
                       prefs={
                           "campaign_start": "2026-01-05",
                           "campaign_end": "2026-01-18",  # 14 days
                           "channel_spots_per_day": [{"channel": "GECbig", "spots_per_day": 1}],
                       })
        invariant(gen)
        assert len(gen["schedule_rows"]) == 500
        # Must be capped to <=2 weeks worth of days
        n_days = len(Counter(s["date"] for s in gen["schedule_rows"]))
        assert n_days <= 14, f"expected <=14 days, got {n_days}"

    def test_stricter_of_gec_planning_weeks_and_channel_spots_per_day_wins(self):
        # channel_spots_per_day says: 280/10 = 28 days = 4 weeks
        # gec_planning_weeks says: 2 weeks
        # -> stricter=2 weeks (14 days)
        rows = [{
            "Market": "HIN", "Genre": "GEC", "Channel": "Star Plus", "Program": "Prime",
            "Days": "Mon-Sun", "Start Time": "19:00", "End Time": "23:00",
            "Net Rate 10Sec": 5000, "ACD": 10, "Spots": 280, "FCT": 2800,
        }]
        d = upload_plan(rows)
        gen = generate(d["plan_id"],
                       edits=[{"duration": 10, "percentage": 100}],
                       prefs={
                           "campaign_start": "2026-01-05",
                           "campaign_end": "2026-03-01",  # 8 weeks nominal
                           "gec_planning_weeks": 2,
                           "channel_spots_per_day": [{"channel": "Star Plus", "spots_per_day": 10}],
                       })
        invariant(gen)
        assert len(gen["schedule_rows"]) == 280
        n_days = len(Counter(s["date"] for s in gen["schedule_rows"]))
        assert n_days <= 14, f"gec_planning_weeks=2 should cap to <=14 days, got {n_days}"

    def test_stricter_reverse_channel_stricter(self):
        # gec_planning_weeks = 8 weeks; channel_spots_per_day says 4 weeks -> channel wins
        rows = [{
            "Market": "HIN", "Genre": "GEC", "Channel": "Star Plus", "Program": "Prime",
            "Days": "Mon-Sun", "Start Time": "19:00", "End Time": "23:00",
            "Net Rate 10Sec": 5000, "ACD": 10, "Spots": 280, "FCT": 2800,
        }]
        d = upload_plan(rows)
        gen = generate(d["plan_id"],
                       edits=[{"duration": 10, "percentage": 100}],
                       prefs={
                           "campaign_start": "2026-01-05",
                           "campaign_end": "2026-03-01",
                           "gec_planning_weeks": 8,
                           "channel_spots_per_day": [{"channel": "Star Plus", "spots_per_day": 10}],
                       })
        invariant(gen)
        n_days = len(Counter(s["date"] for s in gen["schedule_rows"]))
        assert 25 <= n_days <= 30, f"channel cap of ~28 days should apply, got {n_days}"

    def test_multi_channel_multi_genre_end_to_end(self):
        rows = [
            {"Market": "HIN", "Genre": "GEC", "Channel": "Star Plus", "Program": "SP1",
             "Days": "Mon-Sun", "Start Time": "19:00", "End Time": "23:00",
             "Net Rate 10Sec": 5000, "ACD": 10, "Spots": 100, "FCT": 1000},
            {"Market": "HIN", "Genre": "GEC", "Channel": "Colors", "Program": "C1",
             "Days": "Mon-Sun", "Start Time": "20:00", "End Time": "22:00",
             "Net Rate 10Sec": 4000, "ACD": 10, "Spots": 80, "FCT": 800},
            {"Market": "HIN", "Genre": "Movies", "Channel": "Sony Max", "Program": "M1",
             "Days": "Mon-Sun", "Start Time": "21:00", "End Time": "23:00",
             "Net Rate 10Sec": 3000, "ACD": 10, "Spots": 60, "FCT": 600},
            {"Market": "HIN", "Genre": "News", "Channel": "Aaj Tak", "Program": "N1",
             "Days": "Mon-Sun", "Start Time": "20:00", "End Time": "22:00",
             "Net Rate 10Sec": 2000, "ACD": 10, "Spots": 42, "FCT": 420},
            {"Market": "HIN", "Genre": "Music", "Channel": "MTV", "Program": "Mu1",
             "Days": "Mon-Sun", "Start Time": "18:00", "End Time": "20:00",
             "Net Rate 10Sec": 1000, "ACD": 10, "Spots": 30, "FCT": 300},
        ]
        d = upload_plan(rows)
        gen = generate(d["plan_id"],
                       edits=[{"duration": 10, "percentage": 100}],
                       prefs={
                           "campaign_start": "2026-01-05",
                           "campaign_end": "2026-02-15",
                           "movies_frequency_minutes": 60,
                           "channel_spots_per_day": [
                               {"channel": "Star Plus", "spots_per_day": 5},
                               {"channel": "Sony Max", "spots_per_day": 5},
                           ],
                       })
        invariant(gen)
        sr = gen["schedule_rows"]
        assert len(sr) == 100 + 80 + 60 + 42 + 30
        # Star Plus 100/5 => ~20 days => 3 weeks (21 days)
        sp_days = len(Counter(s["date"] for s in sr if s["channel"] == "Star Plus"))
        assert 18 <= sp_days <= 22, f"Star Plus days={sp_days}"
        # Sony Max 60/5 => 12 days => 2 weeks (14 days)
        sm_days = len(Counter(s["date"] for s in sr if s["channel"] == "Sony Max"))
        assert 10 <= sm_days <= 14, f"Sony Max days={sm_days}"
