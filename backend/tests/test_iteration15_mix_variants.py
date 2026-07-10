"""Iteration 15 adversarial coverage:
- 10s-heavy mix (10/60, 20/30, 30/10) — previously showed 21 lost.
- 30s-heavy mix (30/60, 20/30, 10/10).
- Balanced mix.
- Per-row overrides — the overridden row's final_spots must still match scheduled.
For each: total_scheduled == sum(final_spots), zero mismatches, and same-edit
slot uniqueness holds per (_row_id, edit_duration, date, spot_time).
"""
import os
from collections import Counter

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://spot-scheduling-hub.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"
SAMPLE = "/tmp/samples/input.xlsx"

BASE_PREFS = {
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


@pytest.fixture(scope="module")
def plan_id():
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
    return r.json()["plan_id"]


def _generate(pid, edits, row_overrides=None):
    payload = {
        "edits": edits,
        "row_overrides": row_overrides or [],
        "prefs": BASE_PREFS,
    }
    r = requests.post(
        f"{API}/plans/{pid}/generate", json=payload, timeout=180
    )
    assert r.status_code == 200, r.text
    return r.json()


def _assert_full_match(result, label):
    counts = Counter()
    for sr in result["schedule_rows"]:
        counts[(sr["_row_id"], sr["edit_duration"])] += 1

    mismatches = []
    total_req = total_sched = 0
    for er in result["edit_rows"]:
        req = int(er["final_spots"])
        sc = counts.get((er["_row_id"], er["edit_duration"]), 0)
        total_req += req
        total_sched += sc
        if sc != req:
            mismatches.append(
                {
                    "row_id": er["_row_id"],
                    "edit": er["edit_duration"],
                    "channel": er.get("channel"),
                    "program": er.get("program"),
                    "final_spots": req,
                    "scheduled": sc,
                    "delta": sc - req,
                }
            )
    print(
        f"[{label}] requested={total_req} scheduled={total_sched} "
        f"lost={total_req - total_sched} mismatches={len(mismatches)}"
    )
    assert total_sched == total_req, (
        f"[{label}] total scheduled ({total_sched}) != requested ({total_req})"
    )
    assert not mismatches, (
        f"[{label}] {len(mismatches)} edit_rows mismatch. First 5: {mismatches[:5]}"
    )


def _assert_slot_unique(result, label):
    dup = Counter()
    for sr in result["schedule_rows"]:
        dup[(sr["_row_id"], sr["edit_duration"], sr["date"], sr["spot_time"])] += 1
    offenders = [(k, v) for k, v in dup.items() if v > 1]
    assert not offenders, (
        f"[{label}] {len(offenders)} same-edit dupes. First 5: {offenders[:5]}"
    )


# ---------- Adversarial mixes ----------
class TestMixes:
    def test_10s_heavy_mix(self, plan_id):
        edits = [
            {"duration": 10, "percentage": 60},
            {"duration": 20, "percentage": 30},
            {"duration": 30, "percentage": 10},
        ]
        result = _generate(plan_id, edits)
        _assert_full_match(result, "10s-heavy")
        _assert_slot_unique(result, "10s-heavy")

    def test_30s_heavy_mix(self, plan_id):
        edits = [
            {"duration": 30, "percentage": 60},
            {"duration": 20, "percentage": 30},
            {"duration": 10, "percentage": 10},
        ]
        result = _generate(plan_id, edits)
        _assert_full_match(result, "30s-heavy")
        _assert_slot_unique(result, "30s-heavy")

    def test_balanced_mix(self, plan_id):
        edits = [
            {"duration": 10, "percentage": 33},
            {"duration": 20, "percentage": 34},
            {"duration": 30, "percentage": 33},
        ]
        result = _generate(plan_id, edits)
        _assert_full_match(result, "balanced")
        _assert_slot_unique(result, "balanced")

    def test_single_edit_mix(self, plan_id):
        edits = [{"duration": 20, "percentage": 100}]
        result = _generate(plan_id, edits)
        _assert_full_match(result, "single-20s")
        _assert_slot_unique(result, "single-20s")


# ---------- Per-row override ----------
class TestRowOverrides:
    def test_override_row_matches_schedule(self, plan_id):
        # Get uploaded rows to pick a valid _row_id
        # (call upload again to get row metadata)
        with open(SAMPLE, "rb") as f:
            files = {
                "file": (
                    "input.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            }
            up = requests.post(f"{API}/plans/upload", files=files, timeout=60).json()
        rows = up.get("rows", [])
        assert rows, "no rows in uploaded plan"
        target_row_id = rows[0]["_row_id"]

        default_edits = [
            {"duration": 10, "percentage": 60},
            {"duration": 20, "percentage": 30},
            {"duration": 30, "percentage": 10},
        ]
        row_overrides = [
            {
                "row_id": target_row_id,
                "edits": [
                    {"duration": 15, "percentage": 50},
                    {"duration": 45, "percentage": 50},
                ],
            }
        ]
        result = _generate(
            up["plan_id"], default_edits, row_overrides=row_overrides
        )
        _assert_full_match(result, "row_overrides")
        _assert_slot_unique(result, "row_overrides")

        # Additionally: assert the override row has ONLY the override edits
        # (durations 15 and 45), not the defaults 10/20/30.
        override_edits = {
            er["edit_duration"]
            for er in result["edit_rows"]
            if er["_row_id"] == target_row_id
        }
        assert override_edits == {15, 45}, (
            f"override row should only have edits 15/45, got {override_edits}"
        )
