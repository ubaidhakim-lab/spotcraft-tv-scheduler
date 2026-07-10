"""Iteration 14 acceptance tests:
Verify that after fixing occupancy key to include edit_duration:
1. For every edit_row, count of schedule_rows with matching (_row_id, edit_duration)
   equals final_spots exactly (zero drops).
2. For every (_row_id, edit_duration, date, spot_time) tuple, count is exactly 1
   (same-edit uniqueness preserved).
3. For same (_row_id, date, spot_time) but different edit_durations, count can be >1
   (different edits may share a slot).
"""
import os
from collections import Counter, defaultdict

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://spot-scheduling-hub.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"
SAMPLE = "/tmp/samples/input.xlsx"


@pytest.fixture(scope="module")
def uploaded_plan():
    with open(SAMPLE, "rb") as f:
        files = {
            "file": (
                "input.xlsx",
                f,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        r = requests.post(f"{API}/plans/upload", files=files, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def result(uploaded_plan):
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
    edits = uploaded_plan.get("default_edits") or [
        {"duration": 10, "percentage": 60},
        {"duration": 20, "percentage": 30},
        {"duration": 30, "percentage": 10},
    ]
    payload = {"edits": edits, "row_overrides": [], "prefs": prefs}
    r = requests.post(
        f"{API}/plans/{uploaded_plan['plan_id']}/generate",
        json=payload,
        timeout=180,
    )
    assert r.status_code == 200, r.text
    return r.json()


# ---------- Test 1: final_spots == actual scheduled per edit_row ----------
class TestFinalSpotsMatch:
    def test_final_spots_matches_scheduled_count_per_edit_row(self, result):
        edit_rows = result["edit_rows"]
        assert len(edit_rows) > 0, "no edit_rows returned"

        counts = Counter()
        for sr in result["schedule_rows"]:
            counts[(sr["_row_id"], sr["edit_duration"])] += 1

        mismatches = []
        total_requested = 0
        total_scheduled = 0
        for er in edit_rows:
            key = (er["_row_id"], er["edit_duration"])
            requested = int(er["final_spots"])
            scheduled = counts.get(key, 0)
            total_requested += requested
            total_scheduled += scheduled
            if scheduled != requested:
                mismatches.append(
                    {
                        "row_id": er["_row_id"],
                        "edit_duration": er["edit_duration"],
                        "program": er.get("program"),
                        "channel": er.get("channel"),
                        "final_spots": requested,
                        "scheduled": scheduled,
                        "delta": scheduled - requested,
                    }
                )

        print(
            f"Total requested={total_requested} scheduled={total_scheduled} "
            f"lost={total_requested - total_scheduled} mismatches={len(mismatches)}"
        )
        assert not mismatches, (
            f"{len(mismatches)} edit_rows with count mismatch. "
            f"First 5: {mismatches[:5]}"
        )
        assert total_scheduled == total_requested


# ---------- Test 2: same-edit slot uniqueness ----------
class TestSameEditSlotUniqueness:
    def test_no_duplicate_slots_per_row_edit_date_time(self, result):
        counts = Counter()
        for sr in result["schedule_rows"]:
            counts[
                (sr["_row_id"], sr["edit_duration"], sr["date"], sr["spot_time"])
            ] += 1
        dupes = [k for k, v in counts.items() if v > 1]
        assert not dupes, (
            f"{len(dupes)} same-edit double-bookings. First 5: {dupes[:5]}"
        )


# ---------- Test 3: multi-edit slot sharing is allowed & observed ----------
class TestMultiEditSlotSharing:
    def test_different_edits_may_share_slot(self, result):
        # Count how many (row_id, date, spot_time) tuples have >1 distinct
        # edit_duration on them. This confirms the fix actually permits sharing
        # (and also isn't required to exist — if nothing shares, that's fine too,
        # so we just log stats and assert the code path doesn't forbid it by
        # checking that the schedule size >= sum of final_spots).
        by_slot = defaultdict(set)
        for sr in result["schedule_rows"]:
            by_slot[(sr["_row_id"], sr["date"], sr["spot_time"])].add(
                sr["edit_duration"]
            )
        shared = {k: v for k, v in by_slot.items() if len(v) > 1}
        total_slots = len(by_slot)
        print(
            f"total slot-groups={total_slots} shared-by-multiple-edits={len(shared)}"
        )
        # No hard assert on shared>0 (depends on data), but assert the property
        # that the total scheduled equals sum(final_spots) — which is only
        # achievable when sharing is permitted for typical densities.
        total_scheduled = len(result["schedule_rows"])
        total_final = sum(int(er["final_spots"]) for er in result["edit_rows"])
        assert total_scheduled == total_final, (
            f"scheduled({total_scheduled}) != sum(final_spots)({total_final})"
        )


# ---------- Test 4: regression - no cross-edit same-edit_duration dupes ----------
class TestChannelProgramTimebandEditUniqueness:
    def test_uniqueness_per_channel_program_timeband_edit(
        self, uploaded_plan, result
    ):
        rows_map = {
            r["_row_id"]: r
            for r in uploaded_plan.get("rows", [])
            if r.get("_row_id") is not None
        }
        occ = defaultdict(Counter)
        for sr in result["schedule_rows"]:
            raw = rows_map.get(sr["_row_id"], {})
            key = (
                sr["channel"],
                sr["program"],
                raw.get("start_time"),
                raw.get("end_time"),
                sr["edit_duration"],
            )
            occ[key][(sr["date"], sr["spot_time"])] += 1
        offenders = []
        for k, c in occ.items():
            for slot, n in c.items():
                if n > 1:
                    offenders.append((k, slot, n))
        assert not offenders, (
            f"{len(offenders)} same-edit program-timeband dupes. "
            f"First 5: {offenders[:5]}"
        )
