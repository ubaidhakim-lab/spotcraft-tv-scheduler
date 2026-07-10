"""Strict monotonic weekend_boost test: 0.5 < 1.0 < 2.0 < 3.0."""
import os
import datetime as dt
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://spot-scheduling-hub.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"
SAMPLE = "/tmp/samples/input.xlsx"


@pytest.fixture(scope="module")
def plan():
    with open(SAMPLE, "rb") as f:
        files = {"file": ("input.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/plans/upload", files=files, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def gen(plan, boost):
    prefs = {
        "campaign_start": "2026-06-29", "campaign_end": "2026-08-16", "campaign_weeks": 7,
        "spot_frequency_minutes": 30, "movies_frequency_minutes": 60,
        "movies_genres": ["MOV", "Movies", "Movie"], "gec_genres": ["GEC"],
        "weekly_grp_dispersion": [], "blackout_days": [], "blackout_dates": [],
        "daypart_weights": [], "weekend_boost": boost, "reach_vs_frequency": 0.5,
    }
    edits = plan.get("default_edits") or [
        {"duration": 10, "percentage": 60},
        {"duration": 20, "percentage": 30},
        {"duration": 30, "percentage": 10},
    ]
    payload = {"edits": edits, "row_overrides": [], "prefs": prefs}
    r = requests.post(f"{API}/plans/{plan['plan_id']}/generate", json=payload, timeout=180)
    assert r.status_code == 200, r.text
    return r.json()


def weekend_pct(res):
    total = len(res["schedule_rows"])
    wknd = sum(1 for sr in res["schedule_rows"] if dt.date.fromisoformat(sr["date"]).weekday() >= 5)
    return wknd / total * 100.0, wknd, total


def test_weekend_boost_strictly_increasing(plan):
    results = {}
    for b in [0.5, 1.0, 2.0, 3.0]:
        res = gen(plan, b)
        pct, wknd, total = weekend_pct(res)
        results[b] = pct
        print(f"boost={b}: weekend={wknd}/{total} = {pct:.2f}%")
    assert results[0.5] < results[1.0] < results[2.0] < results[3.0], (
        f"Not strictly increasing: {results}"
    )
