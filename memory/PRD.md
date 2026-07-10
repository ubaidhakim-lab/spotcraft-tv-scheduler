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
