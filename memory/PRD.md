# ACD Plan Builder - PRD

## Problem Statement
Web app for media planners to break an ACD-based media plan into an Edit-wise plan and schedule day-wise spots. User uploads a plan with columns (Market, Genre, Channel, Program, Days, Start/End Time, Net Rate/10s, ACD, Spots, FCT, Outlay, Log TVR, GRP). App asks for edit-wise FCT dispersion percentages, then arrives at total spots by edit and generates a day-wise schedule accounting for spot frequency, GEC planning window, weekly GRP dispersion, and blackout days.

## User Personas
- **Media Planner** (primary): Uses tool to convert ACD plans to actionable schedules.

## Core Requirements
1. Upload xlsx/csv media plan; auto-map common columns
2. Configure edit dispersion (durations + percentages summing to 100)
3. Set scheduling preferences: campaign start/weeks, spot frequency, GEC frontloading, weekly GRP dispersion, blackout days
4. Break FCT by edit -> spots per row per edit
5. Schedule day-wise spots across weeks with dispersion & constraints
6. Downloadable Excel with Edit-wise + Day-wise sheets

## Implementation Status (Feb 2026 - Iteration 1)
- Backend: FastAPI endpoints for upload / generate / download; column auto-mapping, day/time parsing, edit dispersion math, per-week spot allocation with rounding, GEC frontloading, blackout days, Excel export with 4 sheets.
- Frontend: 4-step wizard (Upload -> Edits -> Prefs -> Results); drag-drop upload, preset edit mixes, weekly GRP % bars, blackout day chips, results dashboard with stat cards, weekly BarChart, edit-wise PieChart, filterable tables, Excel download link.
- Design: Swiss/high-contrast palette (International Klein Blue), Manrope + IBM Plex Sans typography, dense data tables.

## Backlog / Next
- P1: Per-row (per-program) edit dispersion override
- P1: Sample plan learning (upload past schedule -> use as template)
- P2: Daypart-weighted scheduling (bias to prime time)
- P2: Multi-market summary view
- P2: Save/load plan sessions

## Iteration 2 (Feb 2026)
Adapted to real-world file formats + 4 enhancements requested by user.

### Real-file support
- Multi-row header detection (finds row with Program+Channel/Genre)
- Metadata extraction (Client, Brand, Campaign, Period, TG, Markets)
- Correctly canonicalizes columns: Nett Rate/10sec, ACD, Spots (not Cal Spts PD), FCT, Net Outlay, Log TVR, GRP, NGRP, CPRP
- Duplicate column names disambiguated (two "Start Time"/"Days" columns)
- Output preserves original 40+ column layout PLUS injects Edit, Final Spots, Final FCT, Net Outlay Recomputed, GRP Recomputed columns AND a daily date matrix (Mon-Sun × weeks) with 1s where scheduled AND weekly totals + weekly dispersion %

### Enhancements
1. Per-row edit override: Step 2 shows all program rows in a table; click "Edit" opens dialog for custom mix per row. Saved overrides shown as blue badge in Mix column.
2. Learn from sample: Step 1 has "Choose sample" — upload a past output file, backend extracts edit dispersion (by summing spots per edit duration) + weekly dispersion (by summing spots per WK column) and prefills the wizard.
3. Daypart weighting: Step 3 has 7 sliders (Morning..Overnight) 0-3x; slots at higher-weight dayparts are preferred during allocation.
4. Save/load sessions: Header has Sessions/Save buttons. Sessions persist in MongoDB with full edits + row_overrides + prefs, load restores plan + all settings.

### Additional UX
- Front-load and Bell curve preset buttons for weekly dispersion
- Metadata card in Upload summary shows Client/Brand/Campaign
- Row 4 stat cards + weekly bar + edit pie + 3 tabs (Edit-wise, Day-wise Schedule, By Channel)
