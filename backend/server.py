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
from datetime import datetime, timezone, timedelta
import pandas as pd

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

# -------------------- Models --------------------

class PlanRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    market: Optional[str] = None
    genre: Optional[str] = None
    channel: Optional[str] = None
    program: Optional[str] = None
    days: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    net_rate_10s: Optional[float] = 0
    acd: Optional[float] = 0
    spots: Optional[float] = 0
    fct: Optional[float] = 0
    outlay: Optional[float] = 0
    log_tvr: Optional[float] = 0
    grp: Optional[float] = 0

class EditConfig(BaseModel):
    duration: int  # seconds e.g. 30, 20, 10
    percentage: float  # 0-100

class SchedulingPrefs(BaseModel):
    campaign_start: str  # ISO date "YYYY-MM-DD"
    campaign_weeks: int = 4
    spot_frequency_minutes: int = 30  # 1 spot every X min
    gec_genres: List[str] = ["GEC", "Hindi GEC", "General Entertainment"]
    gec_planning_weeks: Optional[int] = None  # None = full campaign
    weekly_grp_dispersion: List[float] = []  # per-week % totaling 100; empty = uniform
    blackout_days: List[str] = []  # e.g. ["Sun"]

class GenerateRequest(BaseModel):
    edits: List[EditConfig]
    prefs: SchedulingPrefs

# -------------------- Helpers --------------------

def normalize_col(c: str) -> str:
    return str(c).strip().lower().replace(" ", "_").replace("/", "_").replace(".", "").replace("-", "_")

COLUMN_ALIASES = {
    "market": ["market"],
    "genre": ["genre"],
    "channel": ["channel"],
    "program": ["program", "programme", "show"],
    "days": ["days", "day"],
    "start_time": ["start_time", "starttime", "start"],
    "end_time": ["end_time", "endtime", "end"],
    "net_rate_10s": ["net_rate_10sec", "net_rate_10s", "netrate", "net_rate", "rate_10s", "rate"],
    "acd": ["acd", "average_commercial_duration"],
    "spots": ["spots", "no_of_spots", "no_spots"],
    "fct": ["fct", "fct_secs", "fct_sec"],
    "outlay": ["outlay", "cost", "value"],
    "log_tvr": ["log_tvr", "tvr", "logtvr"],
    "grp": ["grp", "grps", "cprp"]
}

def map_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = {c: normalize_col(c) for c in df.columns}
    df = df.rename(columns=normalized)
    remap = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if a in df.columns and canonical not in remap.values():
                remap[a] = canonical
                break
    df = df.rename(columns=remap)
    return df

DAY_ALIASES = {
    "mon": "Mon", "monday": "Mon", "m": "Mon",
    "tue": "Tue", "tues": "Tue", "tuesday": "Tue", "t": "Tue",
    "wed": "Wed", "wednesday": "Wed", "w": "Wed",
    "thu": "Thu", "thur": "Thu", "thurs": "Thu", "thursday": "Thu", "th": "Thu",
    "fri": "Fri", "friday": "Fri", "f": "Fri",
    "sat": "Sat", "saturday": "Sat", "s": "Sat",
    "sun": "Sun", "sunday": "Sun", "su": "Sun",
}

DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def parse_days(days_str: str) -> List[str]:
    if not days_str or str(days_str).lower() == "nan":
        return DAY_ORDER[:]
    s = str(days_str).strip().lower()
    if s in ("daily", "all", "all days", "everyday"):
        return DAY_ORDER[:]
    if s in ("mon-fri", "mon-friday", "weekday", "weekdays", "mtwtf"):
        return DAY_ORDER[:5]
    if s in ("sat-sun", "weekend", "weekends"):
        return DAY_ORDER[5:]
    # Try tokenized split by comma/slash/plus/space
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
    s = str(t).strip()
    if not s or s.lower() == "nan":
        return None
    # Handle formats: "18:00", "18:00:00", "6:00 PM", "18.00"
    s = s.replace(".", ":")
    fmt_list = ["%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%I %p"]
    for fmt in fmt_list:
        try:
            dt = datetime.strptime(s.upper(), fmt)
            return timedelta(hours=dt.hour, minutes=dt.minute, seconds=dt.second)
        except ValueError:
            continue
    # numeric HHMM
    try:
        val = float(s)
        # excel time fraction
        if val < 1:
            total = int(val * 86400)
            return timedelta(seconds=total)
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
        if isinstance(v, str) and not v.strip():
            return default
        f = float(v)
        if math.isnan(f):
            return default
        return f
    except Exception:
        return default

# -------------------- Endpoints --------------------

@api_router.get("/")
async def root():
    return {"message": "ACD Plan Builder API"}

@api_router.post("/plans/upload")
async def upload_plan(file: UploadFile = File(...)):
    content = await file.read()
    name = file.filename.lower()
    try:
        if name.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")

    df = map_columns(df)
    df = df.where(pd.notnull(df), None)

    # Build rows
    rows = []
    for i, r in df.iterrows():
        row = {k: (None if pd.isna(v) else v) for k, v in r.to_dict().items()}
        row["_row_id"] = i
        rows.append(row)

    plan_id = str(uuid.uuid4())
    doc = {
        "id": plan_id,
        "filename": file.filename,
        "columns": list(df.columns),
        "rows": rows,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # Convert non-serializable
    def _clean(o):
        if isinstance(o, dict):
            return {k: _clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_clean(v) for v in o]
        if isinstance(o, (pd.Timestamp, datetime)):
            return str(o)
        if isinstance(o, float) and math.isnan(o):
            return None
        return o
    doc = _clean(doc)

    await db.plans.insert_one(doc)

    # summary
    total_fct = sum(safe_num(r.get("fct")) for r in rows)
    total_spots = sum(safe_num(r.get("spots")) for r in rows)
    total_grp = sum(safe_num(r.get("grp")) for r in rows)
    total_outlay = sum(safe_num(r.get("outlay")) for r in rows)

    return {
        "plan_id": plan_id,
        "filename": file.filename,
        "columns": doc["columns"],
        "row_count": len(rows),
        "rows": rows[:100],  # preview
        "summary": {
            "total_fct": total_fct,
            "total_spots": total_spots,
            "total_grp": total_grp,
            "total_outlay": total_outlay,
        }
    }

@api_router.get("/plans/{plan_id}")
async def get_plan(plan_id: str):
    doc = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Plan not found")
    return doc

@api_router.post("/plans/{plan_id}/generate")
async def generate_plan(plan_id: str, req: GenerateRequest):
    doc = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Plan not found")

    edits = req.edits
    total_pct = sum(e.percentage for e in edits)
    if abs(total_pct - 100) > 0.5:
        raise HTTPException(status_code=400, detail=f"Edit percentages must sum to 100 (got {total_pct})")

    prefs = req.prefs
    try:
        camp_start = datetime.strptime(prefs.campaign_start, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid campaign_start (YYYY-MM-DD)")

    # Weekly dispersion normalization
    weeks = max(1, int(prefs.campaign_weeks))
    if prefs.weekly_grp_dispersion and len(prefs.weekly_grp_dispersion) == weeks:
        wk_disp = prefs.weekly_grp_dispersion[:]
    else:
        wk_disp = [100.0 / weeks] * weeks
    ws = sum(wk_disp)
    wk_disp = [w * 100.0 / ws if ws else 0 for w in wk_disp]

    # -------- Edit-wise plan --------
    edit_rows: List[Dict[str, Any]] = []
    for r in doc["rows"]:
        fct = safe_num(r.get("fct"))
        for e in edits:
            edit_fct = fct * (e.percentage / 100.0)
            spots = edit_fct / e.duration if e.duration > 0 else 0
            row = {
                "market": r.get("market"),
                "genre": r.get("genre"),
                "channel": r.get("channel"),
                "program": r.get("program"),
                "days": r.get("days"),
                "start_time": r.get("start_time"),
                "end_time": r.get("end_time"),
                "acd": safe_num(r.get("acd")),
                "edit_duration": e.duration,
                "edit_pct": e.percentage,
                "edit_fct": round(edit_fct, 2),
                "edit_spots": round(spots, 2),
                "edit_spots_int": int(round(spots)),
                "grp_share": round(safe_num(r.get("grp")) * (e.percentage / 100.0), 3),
                "outlay_share": round(safe_num(r.get("outlay")) * (e.percentage / 100.0), 2),
                "_row_id": r.get("_row_id"),
            }
            edit_rows.append(row)

    # -------- Day-wise schedule --------
    # For each edit_row: distribute spots over available days across weeks
    def is_gec(g):
        return any(k.lower() in str(g or "").lower() for k in prefs.gec_genres)

    schedule_rows: List[Dict[str, Any]] = []
    blackout = set(prefs.blackout_days or [])

    for er in edit_rows:
        n_spots = er["edit_spots_int"]
        if n_spots <= 0:
            continue
        days_list = [d for d in parse_days(er["days"]) if d not in blackout]
        if not days_list:
            continue

        st = parse_time(er["start_time"]) or timedelta(hours=6)
        et = parse_time(er["end_time"]) or (st + timedelta(hours=1))
        if et <= st:
            et = st + timedelta(hours=1)

        # slots at spot_frequency inside window
        step = timedelta(minutes=prefs.spot_frequency_minutes)
        slot_times = []
        cur = st
        while cur < et:
            slot_times.append(cur)
            cur += step
        if not slot_times:
            slot_times = [st]

        # Weeks planning: for GEC apply gec_planning_weeks cap
        eff_weeks = weeks
        if is_gec(er["genre"]) and prefs.gec_planning_weeks:
            eff_weeks = min(weeks, prefs.gec_planning_weeks)

        # allocate spots per week using dispersion (over eff_weeks)
        base_disp = wk_disp[:eff_weeks]
        s = sum(base_disp)
        if s == 0:
            base_disp = [100.0 / eff_weeks] * eff_weeks
            s = 100.0
        norm_disp = [x * 100.0 / s for x in base_disp]

        raw = [n_spots * (p / 100.0) for p in norm_disp]
        week_spots = [int(x) for x in raw]
        # remainder distribution
        remainder = n_spots - sum(week_spots)
        fracs = sorted([(raw[i] - week_spots[i], i) for i in range(len(raw))], reverse=True)
        for k in range(remainder):
            week_spots[fracs[k % len(fracs)][1]] += 1

        # For each week, spread spots across available days & slots
        for w_idx, ws_count in enumerate(week_spots):
            if ws_count <= 0:
                continue
            week_start = camp_start + timedelta(days=7 * w_idx)
            # Build (day, date, slot) options
            options = []
            for d in days_list:
                d_offset = DAY_ORDER.index(d)
                d_date = week_start + timedelta(days=d_offset)
                for t in slot_times:
                    options.append((d, d_date, t))
            if not options:
                continue

            # Round-robin distribution across days first, then slots
            # Build day buckets
            buckets: Dict[str, List] = {d: [] for d in days_list}
            for opt in options:
                buckets[opt[0]].append(opt)

            # allocate by iterating days
            allocated = []
            remaining = ws_count
            di = 0
            while remaining > 0:
                d = days_list[di % len(days_list)]
                if buckets[d]:
                    allocated.append(buckets[d].pop(0))
                    remaining -= 1
                    di += 1
                else:
                    # if this day exhausted, remove from cycle
                    days_list_active = [dd for dd in days_list if buckets[dd]]
                    if not days_list_active:
                        # fallback: reuse first slot of first day
                        allocated.append((days_list[0], week_start + timedelta(days=DAY_ORDER.index(days_list[0])), slot_times[0]))
                        remaining -= 1
                    else:
                        days_list = days_list_active
                        di = 0

            for (d, d_date, t) in allocated:
                schedule_rows.append({
                    "week": w_idx + 1,
                    "date": d_date.isoformat(),
                    "day": d,
                    "market": er["market"],
                    "genre": er["genre"],
                    "channel": er["channel"],
                    "program": er["program"],
                    "edit_duration": er["edit_duration"],
                    "spot_time": format_time(t),
                    "start_time": er["start_time"],
                    "end_time": er["end_time"],
                    "daypart": daypart_of(t),
                })

    # Save result to DB
    result_id = str(uuid.uuid4())
    result_doc = {
        "id": result_id,
        "plan_id": plan_id,
        "edits": [e.model_dump() for e in edits],
        "prefs": prefs.model_dump(),
        "edit_rows": edit_rows,
        "schedule_rows": schedule_rows,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.results.insert_one(result_doc)

    # Summaries
    total_edit_fct = sum(r["edit_fct"] for r in edit_rows)
    total_edit_spots = sum(r["edit_spots_int"] for r in edit_rows)
    total_grp = sum(r["grp_share"] for r in edit_rows)
    total_outlay = sum(r["outlay_share"] for r in edit_rows)

    by_edit: Dict[int, Dict[str, float]] = {}
    for e in edits:
        by_edit[e.duration] = {"duration": e.duration, "spots": 0, "fct": 0, "grp": 0, "outlay": 0}
    for r in edit_rows:
        b = by_edit.get(r["edit_duration"])
        if b:
            b["spots"] += r["edit_spots_int"]
            b["fct"] += r["edit_fct"]
            b["grp"] += r["grp_share"]
            b["outlay"] += r["outlay_share"]

    by_week: Dict[int, Dict[str, float]] = {}
    for r in schedule_rows:
        b = by_week.setdefault(r["week"], {"week": r["week"], "spots": 0})
        b["spots"] += 1

    by_channel: Dict[str, Dict[str, float]] = {}
    for r in edit_rows:
        ch = str(r.get("channel") or "Unknown")
        b = by_channel.setdefault(ch, {"channel": ch, "spots": 0, "fct": 0, "outlay": 0})
        b["spots"] += r["edit_spots_int"]
        b["fct"] += r["edit_fct"]
        b["outlay"] += r["outlay_share"]

    return {
        "result_id": result_id,
        "edit_rows": edit_rows,
        "schedule_rows": schedule_rows,
        "summary": {
            "total_edit_fct": round(total_edit_fct, 2),
            "total_edit_spots": total_edit_spots,
            "total_grp": round(total_grp, 3),
            "total_outlay": round(total_outlay, 2),
            "by_edit": list(by_edit.values()),
            "by_week": list(by_week.values()),
            "by_channel": list(by_channel.values()),
        }
    }

def daypart_of(t: timedelta) -> str:
    h = int(t.total_seconds()) // 3600
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

@api_router.get("/results/{result_id}/download")
async def download_result(result_id: str):
    doc = await db.results.find_one({"id": result_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Result not found")

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        pd.DataFrame(doc["edit_rows"]).to_excel(writer, index=False, sheet_name="Edit-wise Plan")
        pd.DataFrame(doc["schedule_rows"]).to_excel(writer, index=False, sheet_name="Day-wise Schedule")
        pd.DataFrame(doc["edits"]).to_excel(writer, index=False, sheet_name="Edit Config")
        prefs_df = pd.DataFrame(list(doc["prefs"].items()), columns=["Preference", "Value"])
        prefs_df.to_excel(writer, index=False, sheet_name="Preferences")

    output.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="acd_plan_{result_id[:8]}.xlsx"'}
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)

@api_router.get("/plans")
async def list_plans():
    plans = await db.plans.find({}, {"_id": 0, "id": 1, "filename": 1, "created_at": 1, "row_count": 1}).sort("created_at", -1).to_list(50)
    for p in plans:
        # get row count
        pass
    return plans

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
