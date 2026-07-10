from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import logging
import math
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta, date, time
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

# -------------------- Models --------------------

class EditConfig(BaseModel):
    duration: int
    percentage: float

class RowOverride(BaseModel):
    row_id: int
    edits: List[EditConfig]

class DaypartWeight(BaseModel):
    daypart: str
    weight: float

class SchedulingPrefs(BaseModel):
    campaign_start: str
    campaign_weeks: int = 6
    spot_frequency_minutes: int = 30
    gec_genres: List[str] = ["GEC"]
    gec_planning_weeks: Optional[int] = None
    weekly_grp_dispersion: List[float] = []
    blackout_days: List[str] = []
    daypart_weights: List[DaypartWeight] = []

class GenerateRequest(BaseModel):
    edits: List[EditConfig]
    row_overrides: List[RowOverride] = []
    prefs: SchedulingPrefs

class SessionSave(BaseModel):
    name: str
    plan_id: str
    edits: List[EditConfig]
    row_overrides: List[RowOverride] = []
    prefs: SchedulingPrefs

# -------------------- Helpers --------------------

DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

DAY_ALIASES = {
    "mon": "Mon", "monday": "Mon", "m": "Mon",
    "tue": "Tue", "tues": "Tue", "tuesday": "Tue",
    "wed": "Wed", "wednesday": "Wed", "w": "Wed",
    "thu": "Thu", "thur": "Thu", "thurs": "Thu", "thursday": "Thu", "th": "Thu",
    "fri": "Fri", "friday": "Fri", "f": "Fri",
    "sat": "Sat", "saturday": "Sat",
    "sun": "Sun", "sunday": "Sun", "su": "Sun",
}

CANONICAL_ALIASES = {
    "market": ["market", "markets"],
    "genre": ["genre"],
    "channel": ["channel"],
    "program": ["program", "programme", "show"],
    "days": ["days", "day"],
    "start_time": ["start_time", "starttime", "start"],
    "end_time": ["end_time", "endtime", "end"],
    "net_rate_10s": ["net_rate_10sec", "nett_rate_10sec", "netrate10sec", "nett_rate_10s", "net_rate", "rate"],
    "acd": ["acd", "average_commercial_duration"],
    "spots": ["spots", "final_spots", "my_disp_spots"],
    "fct": ["fct", "final_fct", "planned_fct_per_tb"],
    "outlay": ["net_outlay", "outlay", "cost"],
    "log_tvr": ["log_tvr", "logtvr", "tvr"],
    "grp": ["grp", "grps"],
    "ngrp": ["ngrp"],
    "cprp": ["cprp"],
    "direct_matrix": ["direct_matrix", "direct"],
    "index_value": ["index_value", "index"],
}

def normalize_key(s: str) -> str:
    return str(s).strip().lower().replace(" ", "_").replace("/", "_").replace(".", "").replace("-", "_").replace("__", "_")

def to_serializable(v):
    if v is None:
        return None
    if isinstance(v, (datetime,)):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, time):
        return v.strftime("%H:%M:%S")
    if isinstance(v, timedelta):
        total = int(v.total_seconds())
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    if isinstance(v, float) and math.isnan(v):
        return None
    return v

def parse_days(days_str) -> List[str]:
    if days_str is None:
        return DAY_ORDER[:]
    s = str(days_str).strip().lower()
    if not s or s == "nan":
        return DAY_ORDER[:]
    if s in ("daily", "all", "all days", "everyday", "mon-sun"):
        return DAY_ORDER[:]
    if s in ("mon-fri", "mon-friday", "weekday", "weekdays", "mtwtf"):
        return DAY_ORDER[:5]
    if s in ("mon-sat", "mon-saturday"):
        return DAY_ORDER[:6]
    if s in ("sat-sun", "weekend", "weekends", "sat,sun", "sat-sunday"):
        return DAY_ORDER[5:]
    if s in ("sun-sat",):
        return DAY_ORDER[:]
    # range like tue-fri
    if "-" in s and "," not in s:
        parts = s.split("-")
        if len(parts) == 2 and parts[0].strip() in DAY_ALIASES and parts[1].strip() in DAY_ALIASES:
            a = DAY_ALIASES[parts[0].strip()]
            b = DAY_ALIASES[parts[1].strip()]
            ia, ib = DAY_ORDER.index(a), DAY_ORDER.index(b)
            if ia <= ib:
                return DAY_ORDER[ia:ib + 1]
            return DAY_ORDER[ia:] + DAY_ORDER[:ib + 1]
    for sep in [",", "/", "+", "|", "&"]:
        s = s.replace(sep, " ")
    tokens = [t for t in s.split() if t]
    result = []
    for t in tokens:
        if t in DAY_ALIASES and DAY_ALIASES[t] not in result:
            result.append(DAY_ALIASES[t])
    return result or DAY_ORDER[:]

def parse_time(t) -> Optional[timedelta]:
    if t is None:
        return None
    if isinstance(t, time):
        return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)
    if isinstance(t, datetime):
        return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)
    if isinstance(t, timedelta):
        return t
    s = str(t).strip()
    if not s or s.lower() == "nan":
        return None
    s = s.replace(".", ":")
    for fmt in ["%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p", "%I:%M%p", "%I %p"]:
        try:
            dt = datetime.strptime(s.upper(), fmt)
            return timedelta(hours=dt.hour, minutes=dt.minute, seconds=dt.second)
        except ValueError:
            continue
    try:
        val = float(s)
        if val < 1:
            return timedelta(seconds=int(val * 86400))
    except Exception:
        pass
    return None

def format_time(td: timedelta) -> str:
    total = int(td.total_seconds()) % 86400
    h = total // 3600
    m = (total % 3600) // 60
    return f"{h:02d}:{m:02d}"

def safe_num(v, default=0.0):
    try:
        if v is None:
            return default
        if isinstance(v, bool):
            return float(v)
        if isinstance(v, str):
            s = v.strip().replace(",", "")
            if not s or s.startswith("#"):
                return default
            return float(s)
        f = float(v)
        if math.isnan(f):
            return default
        return f
    except Exception:
        return default

def daypart_of(td: timedelta) -> str:
    h = int(td.total_seconds()) // 3600
    if 6 <= h < 9:
        return "Morning"
    if 9 <= h < 12:
        return "Late Morning"
    if 12 <= h < 15:
        return "Afternoon"
    if 15 <= h < 18:
        return "Late Afternoon"
    if 18 <= h < 21:
        return "Prime Time"
    if 21 <= h < 24:
        return "Late Prime"
    return "Overnight"

# -------------------- Sheet parsing --------------------

def find_header_row(ws) -> int:
    """Find the row containing column headers. Look for a row that contains 'Program' or ('Genre' AND 'Channel')."""
    max_scan = min(ws.max_row, 25)
    for r in range(1, max_scan + 1):
        vals = [str(c.value).strip().lower() if c.value is not None else "" for c in ws[r]]
        has_program = any("program" == v for v in vals)
        has_channel = any("channel" == v for v in vals)
        has_genre = any("genre" == v for v in vals)
        if has_program and (has_channel or has_genre):
            return r
    return 1  # fallback

def resolve_canonical(header_norm: str) -> Optional[str]:
    for canonical, aliases in CANONICAL_ALIASES.items():
        if header_norm in aliases:
            return canonical
    return None

def read_workbook(content: bytes):
    wb = load_workbook(io.BytesIO(content), data_only=True)
    ws = wb[wb.sheetnames[0]]
    header_row = find_header_row(ws)

    # Read metadata (any rows above header where col2 has a "key" and col3 has value)
    metadata = {}
    for r in range(1, header_row):
        row = ws[r]
        for j in range(0, min(6, len(row))):
            key = row[j].value
            if key and isinstance(key, str) and j + 1 < len(row):
                val = row[j + 1].value
                if val is not None and str(key).strip().lower() in ("client", "brand", "campaign", "period", "campaign period", "tg", "markets", "market"):
                    metadata[str(key).strip()] = to_serializable(val)

    # Read headers
    raw_headers = [c.value for c in ws[header_row]]
    headers = []
    canonical_of = {}
    seen_canonical = set()
    for j, h in enumerate(raw_headers):
        if h is None or str(h).strip() == "":
            headers.append(f"_col{j+1}")
            continue
        base = str(h).strip()
        norm = normalize_key(base)
        canonical = resolve_canonical(norm)
        # If the canonical was already claimed, keep as extra column with suffix
        if canonical and canonical not in seen_canonical:
            seen_canonical.add(canonical)
            canonical_of[base] = canonical
            headers.append(base)
        else:
            # unique-ify duplicate names
            key = base
            k = 2
            while key in headers:
                key = f"{base} ({k})"
                k += 1
            headers.append(key)

    # Read data rows
    raw_rows = []
    parsed_rows = []
    for r in range(header_row + 1, ws.max_row + 1):
        row = ws[r]
        vals = [to_serializable(c.value) for c in row]
        # skip completely empty rows
        if all(v is None or v == "" for v in vals):
            continue
        # skip subtotal/summary rows: if col1 or col-first non-null contains "Total"
        first_text = next((str(v) for v in vals if v is not None), "")
        if "total" in first_text.lower() and not first_text.lower().startswith("total") and "kar" not in first_text.lower():
            # Heuristic: row where any column value contains 'Total' alone
            joined = " ".join(str(v) for v in vals if v is not None)
            if joined.strip().endswith("Total") or " Total " in joined:
                continue
        raw = {}
        for j, v in enumerate(vals):
            if j < len(headers):
                raw[headers[j]] = v
        raw["_row_id"] = len(raw_rows)
        raw_rows.append(raw)

        # Canonical parsed row
        p = {"_row_id": raw["_row_id"]}
        for base, canonical in canonical_of.items():
            v = raw.get(base)
            if canonical in ("net_rate_10s", "acd", "spots", "fct", "outlay", "log_tvr", "grp", "ngrp", "cprp", "index_value"):
                p[canonical] = safe_num(v)
            else:
                p[canonical] = v
        parsed_rows.append(p)

    # Detect skipped subtotals a second way: rows where core fields are all missing
    filtered = []
    filtered_raw = []
    for i, pr in enumerate(parsed_rows):
        # require at least channel or program
        if not pr.get("channel") and not pr.get("program"):
            continue
        # skip if program value contains "Total"
        if pr.get("program") and "total" in str(pr["program"]).lower():
            continue
        filtered.append(pr)
        filtered_raw.append(raw_rows[i])

    # renumber row_id
    for i, r in enumerate(filtered):
        r["_row_id"] = i
    for i, r in enumerate(filtered_raw):
        r["_row_id"] = i

    return {
        "metadata": metadata,
        "header_row": header_row,
        "columns": headers,
        "raw_rows": filtered_raw,
        "parsed_rows": filtered,
    }

# -------------------- Endpoints --------------------

@api_router.get("/")
async def root():
    return {"message": "ACD Plan Builder API"}

@api_router.post("/plans/upload")
async def upload_plan(file: UploadFile = File(...)):
    content = await file.read()
    try:
        parsed = read_workbook(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}") from e

    plan_id = str(uuid.uuid4())
    doc = {
        "id": plan_id,
        "filename": file.filename,
        "metadata": parsed["metadata"],
        "header_row": parsed["header_row"],
        "columns": parsed["columns"],
        "raw_rows": parsed["raw_rows"],
        "parsed_rows": parsed["parsed_rows"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.plans.insert_one(doc)

    rows = parsed["parsed_rows"]
    total_fct = sum(safe_num(r.get("fct")) for r in rows)
    total_spots = sum(safe_num(r.get("spots")) for r in rows)
    total_grp = sum(safe_num(r.get("grp")) for r in rows)
    total_outlay = sum(safe_num(r.get("outlay")) for r in rows)

    return {
        "plan_id": plan_id,
        "filename": file.filename,
        "metadata": parsed["metadata"],
        "columns": parsed["columns"],
        "row_count": len(rows),
        "rows": rows[:200],  # canonical preview
        "raw_preview": parsed["raw_rows"][:20],
        "summary": {
            "total_fct": total_fct,
            "total_spots": total_spots,
            "total_grp": total_grp,
            "total_outlay": total_outlay,
        },
    }

@api_router.post("/plans/learn-sample")
async def learn_sample(file: UploadFile = File(...)):
    """Learn edit dispersion + weekly dispersion from a past output schedule."""
    content = await file.read()
    try:
        wb = load_workbook(io.BytesIO(content), data_only=True)
        ws = wb[wb.sheetnames[0]]
        header_row = find_header_row(ws)
        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[header_row]]
        headers_lower = [h.lower() for h in headers]

        # Find Edit column & Final Spots column
        edit_col = None
        spots_col = None
        for j, h in enumerate(headers_lower):
            if h == "edit":
                edit_col = j
            if h == "final spots" or h == "spots" or h == "cal spts pd":
                if spots_col is None:
                    spots_col = j

        # Sum spots by edit duration
        edit_spots: Dict[int, float] = {}
        # Also detect week columns (WK 1, WK 2 ... in header row 10 area OR find row with "Wk 1" etc)
        week_totals: Dict[int, float] = {}
        # Search for weekly summary columns
        week_cols = []
        for j, h in enumerate(headers_lower):
            if h.startswith("wk ") and h[3:].strip().isdigit():
                week_cols.append((int(h[3:].strip()), j))

        for r in range(header_row + 1, ws.max_row + 1):
            row = ws[r]
            if edit_col is not None and spots_col is not None:
                e = safe_num(row[edit_col].value)
                s = safe_num(row[spots_col].value)
                if e > 0 and s > 0:
                    edit_spots[int(round(e))] = edit_spots.get(int(round(e)), 0) + s
            for wk_num, jcol in week_cols:
                v = safe_num(row[jcol].value)
                week_totals[wk_num] = week_totals.get(wk_num, 0) + v

        total_spots = sum(edit_spots.values())
        edits = []
        if total_spots > 0:
            for dur, sp in sorted(edit_spots.items(), key=lambda x: -x[1]):
                edits.append({"duration": dur, "percentage": round(sp * 100.0 / total_spots, 2)})

        wk_disp = []
        if week_totals:
            wk_total = sum(week_totals.values())
            if wk_total > 0:
                for w in sorted(week_totals.keys()):
                    wk_disp.append(round(week_totals[w] * 100.0 / wk_total, 2))

        return {
            "edits": edits,
            "weekly_grp_dispersion": wk_disp,
            "campaign_weeks": len(wk_disp) if wk_disp else 0,
            "source_filename": file.filename,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to learn from sample: {e}")

@api_router.get("/plans/{plan_id}")
async def get_plan(plan_id: str):
    doc = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Plan not found")
    return doc

def apply_daypart_weights(slot_times: List[timedelta], weights: Dict[str, float]) -> List[float]:
    if not weights:
        return [1.0] * len(slot_times)
    out = []
    for t in slot_times:
        dp = daypart_of(t)
        w = weights.get(dp, 1.0)
        out.append(max(0.01, w))
    total = sum(out)
    if total <= 0:
        return [1.0] * len(slot_times)
    return [x / total * len(slot_times) for x in out]

def allocate_spots_daily(days_list: List[str], slot_times: List[timedelta], slot_weights: List[float], count: int, week_start: date):
    """Return list of (day_name, date, timedelta) for scheduled spots."""
    # For each day, generate weighted slot list
    day_dates = {d: week_start + timedelta(days=DAY_ORDER.index(d)) for d in days_list}
    # Build weighted pool of (day, date, time, weight)
    pool = []
    for d in days_list:
        for i, t in enumerate(slot_times):
            pool.append((d, day_dates[d], t, slot_weights[i]))
    if not pool:
        return []
    # Simple round-robin across days, and within a day pick highest-weight slots first
    by_day = {d: [] for d in days_list}
    for d, dt, t, w in pool:
        by_day[d].append((w, t, dt))
    for d in by_day:
        by_day[d].sort(key=lambda x: (-x[0], x[1]))
    allocated = []
    # round-robin day loop; if a day exhausted, remove
    di = 0
    active_days = [d for d in days_list if by_day[d]]
    while count > 0 and active_days:
        d = active_days[di % len(active_days)]
        w, t, dt = by_day[d].pop(0)
        allocated.append((d, dt, t))
        count -= 1
        di += 1
        if not by_day[d]:
            active_days = [x for x in active_days if by_day[x]]
            di = 0
    # If we still have spots remaining and no slots left, cycle back
    while count > 0:
        d = days_list[0]
        allocated.append((d, day_dates[d], slot_times[0]))
        count -= 1
    return allocated

@api_router.post("/plans/{plan_id}/generate")
async def generate_plan(plan_id: str, req: GenerateRequest):
    doc = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Plan not found")

    edits_global = req.edits
    total_pct = sum(e.percentage for e in edits_global)
    if abs(total_pct - 100) > 0.5:
        raise HTTPException(status_code=400, detail=f"Edit percentages must sum to 100 (got {total_pct})")

    # Row overrides
    override_map: Dict[int, List[EditConfig]] = {}
    for ov in req.row_overrides:
        s = sum(e.percentage for e in ov.edits)
        if abs(s - 100) > 0.5:
            raise HTTPException(status_code=400, detail=f"Row {ov.row_id} override percentages must sum to 100 (got {s})")
        override_map[ov.row_id] = ov.edits

    prefs = req.prefs
    try:
        camp_start = datetime.strptime(prefs.campaign_start, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid campaign_start (YYYY-MM-DD)")
    # Align to Monday of that week for cleaner weekly grouping
    camp_start_monday = camp_start - timedelta(days=camp_start.weekday())

    weeks = max(1, int(prefs.campaign_weeks))
    if prefs.weekly_grp_dispersion and len(prefs.weekly_grp_dispersion) == weeks:
        wk_disp = prefs.weekly_grp_dispersion[:]
    else:
        wk_disp = [100.0 / weeks] * weeks
    ws_sum = sum(wk_disp)
    wk_disp = [w * 100.0 / ws_sum if ws_sum else 0 for w in wk_disp]

    daypart_weight_map = {d.daypart: d.weight for d in prefs.daypart_weights} if prefs.daypart_weights else {}

    def is_gec(g):
        return any(k.lower() in str(g or "").lower() for k in prefs.gec_genres)

    edit_rows: List[Dict[str, Any]] = []
    for r in doc["parsed_rows"]:
        fct = safe_num(r.get("fct"))
        spots_total = safe_num(r.get("spots"))
        grp_total = safe_num(r.get("grp"))
        rate_10s = safe_num(r.get("net_rate_10s"))
        acd = safe_num(r.get("acd")) or 10

        # Determine actual FCT if missing: spots × ACD
        if fct <= 0 and spots_total > 0 and acd > 0:
            fct = spots_total * acd

        row_edits = override_map.get(r["_row_id"], edits_global)
        # Base per-spot GRP: original GRP / original spots (if any)
        per_spot_grp = (grp_total / spots_total) if spots_total > 0 else 0

        for e in row_edits:
            edit_fct = fct * (e.percentage / 100.0)
            spots = edit_fct / e.duration if e.duration > 0 else 0
            spots_int = int(round(spots))
            final_fct = spots_int * e.duration
            net_outlay = final_fct * (rate_10s / 10.0)
            grp_share = spots_int * per_spot_grp

            edit_rows.append({
                "_row_id": r["_row_id"],
                "direct_matrix": r.get("direct_matrix"),
                "index_value": r.get("index_value") or (r["_row_id"] + 1),
                "market": r.get("market"),
                "genre": r.get("genre"),
                "channel": r.get("channel"),
                "program": r.get("program"),
                "days": r.get("days"),
                "start_time": r.get("start_time"),
                "end_time": r.get("end_time"),
                "net_rate_10s": rate_10s,
                "acd": acd,
                "edit_duration": e.duration,
                "edit_pct": e.percentage,
                "final_spots": spots_int,
                "final_fct": round(final_fct, 2),
                "net_outlay": round(net_outlay, 2),
                "grp": round(grp_share, 4),
                "log_tvr": safe_num(r.get("log_tvr")),
            })

    # -------- Day-wise schedule --------
    schedule_rows: List[Dict[str, Any]] = []
    blackout = set(prefs.blackout_days or [])

    for er in edit_rows:
        n_spots = er["final_spots"]
        if n_spots <= 0:
            continue
        days_list = [d for d in parse_days(er.get("days")) if d not in blackout]
        if not days_list:
            continue

        st = parse_time(er.get("start_time")) or timedelta(hours=6)
        et = parse_time(er.get("end_time")) or (st + timedelta(hours=1))
        if et <= st:
            et = st + timedelta(hours=1)

        step = timedelta(minutes=max(5, prefs.spot_frequency_minutes))
        slot_times = []
        cur = st
        while cur < et:
            slot_times.append(cur)
            cur += step
        if not slot_times:
            slot_times = [st]
        slot_weights = apply_daypart_weights(slot_times, daypart_weight_map)

        eff_weeks = weeks
        if is_gec(er.get("genre")) and prefs.gec_planning_weeks:
            eff_weeks = min(weeks, prefs.gec_planning_weeks)

        base_disp = wk_disp[:eff_weeks]
        s = sum(base_disp)
        if s == 0:
            base_disp = [100.0 / eff_weeks] * eff_weeks
            s = 100.0
        norm_disp = [x * 100.0 / s for x in base_disp]
        raw = [n_spots * (p / 100.0) for p in norm_disp]
        week_spots = [int(x) for x in raw]
        remainder = n_spots - sum(week_spots)
        fracs = sorted([(raw[i] - week_spots[i], i) for i in range(len(raw))], reverse=True)
        for k in range(remainder):
            week_spots[fracs[k % len(fracs)][1]] += 1

        for w_idx, ws_count in enumerate(week_spots):
            if ws_count <= 0:
                continue
            week_start = camp_start_monday + timedelta(days=7 * w_idx)
            allocated = allocate_spots_daily(days_list, slot_times, slot_weights, ws_count, week_start)
            for (d, d_date, t) in allocated:
                schedule_rows.append({
                    "_row_id": er["_row_id"],
                    "index_value": er["index_value"],
                    "edit_duration": er["edit_duration"],
                    "week": w_idx + 1,
                    "date": d_date.isoformat(),
                    "day": d,
                    "market": er.get("market"),
                    "genre": er.get("genre"),
                    "channel": er.get("channel"),
                    "program": er.get("program"),
                    "spot_time": format_time(t),
                    "daypart": daypart_of(t),
                })

    # Save result
    result_id = str(uuid.uuid4())
    result_doc = {
        "id": result_id,
        "plan_id": plan_id,
        "edits": [e.model_dump() for e in edits_global],
        "row_overrides": [ov.model_dump() for ov in req.row_overrides],
        "prefs": prefs.model_dump(),
        "campaign_start_monday": camp_start_monday.isoformat(),
        "edit_rows": edit_rows,
        "schedule_rows": schedule_rows,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.results.insert_one(result_doc)

    total_edit_fct = sum(r["final_fct"] for r in edit_rows)
    total_edit_spots = sum(r["final_spots"] for r in edit_rows)
    total_grp = sum(r["grp"] for r in edit_rows)
    total_outlay = sum(r["net_outlay"] for r in edit_rows)

    by_edit: Dict[int, Dict[str, float]] = {}
    for r in edit_rows:
        b = by_edit.setdefault(r["edit_duration"], {"duration": r["edit_duration"], "spots": 0, "fct": 0, "grp": 0, "outlay": 0})
        b["spots"] += r["final_spots"]
        b["fct"] += r["final_fct"]
        b["grp"] += r["grp"]
        b["outlay"] += r["net_outlay"]

    by_week: Dict[int, Dict[str, float]] = {}
    for r in schedule_rows:
        b = by_week.setdefault(r["week"], {"week": r["week"], "spots": 0})
        b["spots"] += 1
    # Fill missing weeks with 0
    for w in range(1, weeks + 1):
        by_week.setdefault(w, {"week": w, "spots": 0})
    by_week_list = [by_week[w] for w in sorted(by_week.keys())]

    by_channel: Dict[str, Dict[str, float]] = {}
    for r in edit_rows:
        ch = str(r.get("channel") or "Unknown")
        b = by_channel.setdefault(ch, {"channel": ch, "spots": 0, "fct": 0, "outlay": 0, "grp": 0})
        b["spots"] += r["final_spots"]
        b["fct"] += r["final_fct"]
        b["outlay"] += r["net_outlay"]
        b["grp"] += r["grp"]

    by_daypart: Dict[str, Dict[str, float]] = {}
    for r in schedule_rows:
        b = by_daypart.setdefault(r["daypart"], {"daypart": r["daypart"], "spots": 0})
        b["spots"] += 1

    return {
        "result_id": result_id,
        "edit_rows": edit_rows,
        "schedule_rows": schedule_rows,
        "campaign_start_monday": camp_start_monday.isoformat(),
        "summary": {
            "total_edit_fct": round(total_edit_fct, 2),
            "total_edit_spots": total_edit_spots,
            "total_grp": round(total_grp, 3),
            "total_outlay": round(total_outlay, 2),
            "by_edit": list(by_edit.values()),
            "by_week": by_week_list,
            "by_channel": list(by_channel.values()),
            "by_daypart": list(by_daypart.values()),
        }
    }

# -------------------- Excel export in original format --------------------

def build_output_workbook(plan_doc: Dict[str, Any], result_doc: Dict[str, Any]) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Schedule Sheet"

    metadata = plan_doc.get("metadata", {})
    columns = plan_doc.get("columns", [])
    raw_rows = plan_doc.get("raw_rows", [])
    edit_rows = result_doc["edit_rows"]
    schedule_rows = result_doc["schedule_rows"]
    prefs = result_doc["prefs"]
    weeks = int(prefs.get("campaign_weeks", 6))
    camp_start = datetime.fromisoformat(result_doc["campaign_start_monday"]).date()

    # Styling
    bold = Font(bold=True)
    header_fill = PatternFill("solid", fgColor="002FA7")
    header_font = Font(bold=True, color="FFFFFF")
    center = Alignment(horizontal="center", vertical="center")

    # Metadata rows
    row = 1
    for k, v in metadata.items():
        ws.cell(row=row, column=2, value=k).font = bold
        ws.cell(row=row, column=3, value=str(v))
        row += 1
    row += 1  # gap

    # Determine columns to write in the header
    # Insert "Edit", "Final Spots", "Final FCT", "Net Outlay", "GRP" after original columns
    output_cols = list(columns)
    extra_cols = ["Edit", "Final Spots", "Final FCT", "Net Outlay Recomputed", "GRP Recomputed"]
    # Build daily date columns
    n_days = weeks * 7
    date_cols = [(camp_start + timedelta(days=i)) for i in range(n_days)]
    week_summary_start_label = "Weekly Spots"
    week_disp_label = "Weekly Spot Dispersion"

    # Header row
    header_row_idx = row
    # write week banner
    for w in range(weeks):
        c_start = len(output_cols) + len(extra_cols) + 1 + w * 7 + 1
        ws.cell(row=row, column=c_start, value=f"Wk {w+1}").font = bold
    row += 1
    # Days row (Mon-Sun repeating)
    for i, dt in enumerate(date_cols):
        col = len(output_cols) + len(extra_cols) + 1 + i + 1
        ws.cell(row=row, column=col, value=DAY_ORDER[dt.weekday()]).font = bold
    row += 1

    # Column names row
    col_names_row = row
    for j, name in enumerate(output_cols):
        c = ws.cell(row=col_names_row, column=j + 1, value=name)
        c.font = header_font
        c.fill = header_fill
        c.alignment = center
    for j, name in enumerate(extra_cols):
        c = ws.cell(row=col_names_row, column=len(output_cols) + j + 1, value=name)
        c.font = header_font
        c.fill = header_fill
        c.alignment = center
    # date columns
    date_col_start = len(output_cols) + len(extra_cols) + 1
    for i, dt in enumerate(date_cols):
        c = ws.cell(row=col_names_row, column=date_col_start + i, value=dt)
        c.font = header_font
        c.fill = header_fill
        c.alignment = center
        c.number_format = "yyyy-mm-dd"
    # week summary columns
    ws_start = date_col_start + n_days + 1
    ws.cell(row=header_row_idx, column=ws_start, value=week_summary_start_label).font = bold
    for w in range(weeks):
        c = ws.cell(row=col_names_row, column=ws_start + w, value=f"Wk {w+1}")
        c.font = header_font
        c.fill = header_fill
    disp_start = ws_start + weeks + 1
    ws.cell(row=header_row_idx, column=disp_start, value=week_disp_label).font = bold
    for w in range(weeks):
        c = ws.cell(row=col_names_row, column=disp_start + w, value=f"Wk {w+1}")
        c.font = header_font
        c.fill = header_fill

    row = col_names_row + 1

    # Index raw rows by _row_id for lookup
    raw_by_id = {r["_row_id"]: r for r in raw_rows}
    # Index schedule spots per (row_id, edit_duration, date)
    sched_index: Dict[tuple, int] = {}
    for s in schedule_rows:
        key = (s["_row_id"], s["edit_duration"], s["date"])
        sched_index[key] = sched_index.get(key, 0) + 1

    date_iso_list = [d.isoformat() for d in date_cols]

    # Emit edit sub-rows grouped by row_id
    grouped: Dict[int, List[Dict]] = {}
    for er in edit_rows:
        grouped.setdefault(er["_row_id"], []).append(er)

    for rid in sorted(grouped.keys()):
        for er in grouped[rid]:
            raw = raw_by_id.get(rid, {})
            # Write original columns
            for j, cname in enumerate(output_cols):
                v = raw.get(cname)
                ws.cell(row=row, column=j + 1, value=v)
            # Extra columns
            base = len(output_cols)
            ws.cell(row=row, column=base + 1, value=er["edit_duration"])
            ws.cell(row=row, column=base + 2, value=er["final_spots"])
            ws.cell(row=row, column=base + 3, value=er["final_fct"])
            ws.cell(row=row, column=base + 4, value=er["net_outlay"])
            ws.cell(row=row, column=base + 5, value=er["grp"])

            # Daily matrix
            weekly_counts = [0] * weeks
            for i, iso in enumerate(date_iso_list):
                n = sched_index.get((rid, er["edit_duration"], iso), 0)
                if n:
                    ws.cell(row=row, column=date_col_start + i, value=n)
                    weekly_counts[i // 7] += n

            total_week = sum(weekly_counts)
            for w in range(weeks):
                ws.cell(row=row, column=ws_start + w, value=weekly_counts[w])
            for w in range(weeks):
                pct = (weekly_counts[w] * 100.0 / total_week) if total_week else 0
                ws.cell(row=row, column=disp_start + w, value=round(pct, 2))

            row += 1

    # column widths
    for j in range(1, min(len(output_cols) + len(extra_cols) + 1, 50)):
        ws.column_dimensions[ws.cell(row=col_names_row, column=j).column_letter].width = 14

    # Add a second sheet: Edit Config + Preferences
    ws2 = wb.create_sheet("Edit Config")
    ws2.append(["Duration (s)", "Percentage"])
    for e in result_doc["edits"]:
        ws2.append([e["duration"], e["percentage"]])

    ws3 = wb.create_sheet("Preferences")
    for k, v in prefs.items():
        ws3.append([k, str(v)])

    return wb

@api_router.get("/results/{result_id}/download")
async def download_result(result_id: str):
    result_doc = await db.results.find_one({"id": result_id}, {"_id": 0})
    if not result_doc:
        raise HTTPException(status_code=404, detail="Result not found")
    plan_doc = await db.plans.find_one({"id": result_doc["plan_id"]}, {"_id": 0})
    if not plan_doc:
        raise HTTPException(status_code=404, detail="Plan not found")

    wb = build_output_workbook(plan_doc, result_doc)
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="acd_schedule_{result_id[:8]}.xlsx"'}
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )

# -------------------- Sessions --------------------

@api_router.post("/sessions")
async def save_session(s: SessionSave):
    session_id = str(uuid.uuid4())
    doc = {
        "id": session_id,
        "name": s.name,
        "plan_id": s.plan_id,
        "edits": [e.model_dump() for e in s.edits],
        "row_overrides": [ov.model_dump() for ov in s.row_overrides],
        "prefs": s.prefs.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.sessions.insert_one(doc)
    return {"id": session_id, "name": s.name}

@api_router.get("/sessions")
async def list_sessions():
    items = await db.sessions.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return items

@api_router.get("/sessions/{sid}")
async def get_session(sid: str):
    doc = await db.sessions.find_one({"id": sid}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    return doc

@api_router.delete("/sessions/{sid}")
async def delete_session(sid: str):
    await db.sessions.delete_one({"id": sid})
    return {"ok": True}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
