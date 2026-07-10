import { useEffect, useMemo } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";

export default function StepPrefs({ prefs, setPrefs, upload }) {
  const setKey = (k, v) => setPrefs({ ...prefs, [k]: v });

  // Derive weeks from start/end date if both are set, else fall back to campaign_weeks
  const derivedWeeks = (() => {
    if (prefs.campaign_start && prefs.campaign_end) {
      const s = new Date(prefs.campaign_start);
      const e = new Date(prefs.campaign_end);
      if (!isNaN(s) && !isNaN(e) && e >= s) {
        const days = Math.floor((e - s) / (24 * 3600 * 1000)) + 1;
        return Math.max(1, Math.ceil(days / 7));
      }
    }
    return Math.max(1, prefs.campaign_weeks || 1);
  })();
  const weeks = derivedWeeks;

  useEffect(() => {
    setPrefs((p) => {
      const patch = {};
      if (p.campaign_weeks !== weeks) patch.campaign_weeks = weeks;
      if (p.weekly_grp_dispersion.length !== weeks) {
        const base = 100 / weeks;
        patch.weekly_grp_dispersion = Array.from({ length: weeks }, () => Number(base.toFixed(2)));
      }
      if (Object.keys(patch).length === 0) return p;
      return { ...p, ...patch };
    });
  }, [weeks, setPrefs]);

  const setWeek = (i, val) => {
    const arr = [...prefs.weekly_grp_dispersion];
    arr[i] = parseFloat(val || 0);
    setKey("weekly_grp_dispersion", arr);
  };

  // Blackout dates: user types DD-MM-YY (or DD-MM-YYYY) comma/space separated.
  // We store as ISO YYYY-MM-DD.
  const parseDDMMYY = (s) => {
    const parts = s.trim().split(/[-/.]/);
    if (parts.length !== 3) return null;
    let [dd, mm, yy] = parts;
    if (dd.length > 2 && yy.length <= 2) {
      const y = dd, d = yy;
      dd = d;
      yy = y;
    }
    const d = parseInt(dd, 10);
    const m = parseInt(mm, 10);
    let y = parseInt(yy, 10);
    if (isNaN(d) || isNaN(m) || isNaN(y)) return null;
    if (y < 100) y += 2000;
    if (d < 1 || d > 31 || m < 1 || m > 12) return null;
    return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  };

  const formatDDMMYY = (iso) => {
    if (!iso) return "";
    const [y, m, d] = iso.split("-");
    return `${d}-${m}-${y.slice(2)}`;
  };

  const onBlackoutDatesChange = (text) => setKey("_blackout_dates_text", text);
  const commitBlackoutDates = () => {
    const raw = prefs._blackout_dates_text ?? prefs.blackout_dates.map(formatDDMMYY).join(", ");
    const tokens = raw.split(/[,;\n]+/).map((t) => t.trim()).filter(Boolean);
    const iso = [];
    for (const t of tokens) {
      const p = parseDDMMYY(t);
      if (p) iso.push(p);
    }
    setPrefs({ ...prefs, blackout_dates: iso, _blackout_dates_text: undefined });
  };
  const blackoutDatesText =
    prefs._blackout_dates_text !== undefined
      ? prefs._blackout_dates_text
      : (prefs.blackout_dates || []).map(formatDDMMYY).join(", ");

  const gecOnly = !!prefs.gec_planning_weeks;
  const weeklyTotal = prefs.weekly_grp_dispersion.reduce((a, b) => a + Number(b || 0), 0);

  // -------- Genre → channels map derived from uploaded plan --------
  const genreChannels = useMemo(() => {
    const map = new Map(); // genre -> ordered Set of channels
    for (const row of upload?.rows || []) {
      const g = String(row.genre || "Uncategorized").trim() || "Uncategorized";
      const ch = String(row.channel || "").trim();
      if (!ch) continue;
      if (!map.has(g)) map.set(g, new Set());
      map.get(g).add(ch);
    }
    return Array.from(map.entries()).map(([genre, chSet]) => ({
      genre,
      channels: Array.from(chSet),
    }));
  }, [upload]);

  const spotsPerDayFor = (channel) => {
    const found = (prefs.channel_spots_per_day || []).find((x) => x.channel === channel);
    return found ? found.spots_per_day : "";
  };

  const setSpotsPerDay = (channel, val) => {
    const parsed = val === "" || val === null || val === undefined ? 0 : parseFloat(val);
    const list = (prefs.channel_spots_per_day || []).filter((x) => x.channel !== channel);
    if (parsed > 0) list.push({ channel, spots_per_day: parsed });
    setKey("channel_spots_per_day", list);
  };

  const applyToGenre = (genre, channels, val) => {
    const parsed = parseFloat(val || 0);
    const others = (prefs.channel_spots_per_day || []).filter(
      (x) => !channels.includes(x.channel)
    );
    const added = parsed > 0 ? channels.map((c) => ({ channel: c, spots_per_day: parsed })) : [];
    setKey("channel_spots_per_day", [...others, ...added]);
  };

  const clearAllChannelRates = () => setKey("channel_spots_per_day", []);

  const totalChannels = genreChannels.reduce((a, g) => a + g.channels.length, 0);
  const filledChannels = (prefs.channel_spots_per_day || []).filter((x) => x.spots_per_day > 0).length;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <section className="bg-white border border-border p-8">
        <div className="overline mb-2">Step 3 · Scheduling Preferences</div>
        <h2 className="font-display text-3xl font-extrabold tracking-tight">
          Campaign & pacing
        </h2>
        <p className="text-muted-foreground mt-2 text-sm">
          Set the window and daily rate per channel. We&apos;ll auto-shape the schedule.
        </p>

        <div className="mt-6 grid grid-cols-2 gap-4">
          <div>
            <Label className="overline">Campaign start</Label>
            <Input
              type="date"
              value={prefs.campaign_start}
              onChange={(e) => setKey("campaign_start", e.target.value)}
              className="mt-1"
              data-testid="campaign-start-input"
            />
          </div>
          <div>
            <Label className="overline">Campaign end</Label>
            <Input
              type="date"
              value={prefs.campaign_end || ""}
              onChange={(e) => setKey("campaign_end", e.target.value)}
              className="mt-1"
              data-testid="campaign-end-input"
            />
          </div>
        </div>
        <p className="text-xs text-muted-foreground mt-2 tabular">
          Duration: <span className="font-semibold text-foreground">{weeks} week{weeks !== 1 ? "s" : ""}</span>
          {" · schedule starts on "}
          <span className="font-semibold text-foreground">{prefs.campaign_start || "—"}</span>
        </p>

        <div className="mt-6">
          <Label className="overline">Spot frequency</Label>
          <div className="mt-2 flex items-center gap-3">
            <span className="text-sm text-muted-foreground">1 spot every</span>
            <Input
              type="number"
              min="5"
              step="5"
              value={prefs.spot_frequency_minutes}
              onChange={(e) => setKey("spot_frequency_minutes", parseInt(e.target.value || 30))}
              className="w-24 tabular"
              data-testid="spot-frequency-input"
            />
            <span className="text-sm text-muted-foreground">minutes</span>
          </div>
        </div>

        <div className="mt-6 border-t border-border pt-6">
          <div className="flex items-center justify-between">
            <div>
              <Label className="overline">Limit GEC to first N weeks</Label>
              <p className="text-xs text-muted-foreground mt-1">
                Frontload spots on General Entertainment channels
              </p>
            </div>
            <Switch
              checked={gecOnly}
              onCheckedChange={(v) => setKey("gec_planning_weeks", v ? Math.min(2, weeks) : null)}
              data-testid="gec-limit-switch"
            />
          </div>
          {gecOnly && (
            <div className="mt-3 flex items-center gap-3">
              <span className="text-sm text-muted-foreground">Plan GEC in first</span>
              <Input
                type="number"
                min="1"
                max={weeks}
                value={prefs.gec_planning_weeks}
                onChange={(e) => setKey("gec_planning_weeks", parseInt(e.target.value || 1))}
                className="w-20 tabular"
                data-testid="gec-weeks-input"
              />
              <span className="text-sm text-muted-foreground">weeks (of {weeks})</span>
            </div>
          )}
        </div>

        <div className="mt-6 border-t border-border pt-6">
          <Label className="overline">Blackout dates (DD-MM-YY)</Label>
          <p className="text-xs text-muted-foreground mt-1">
            Specific dates to skip. Enter comma-separated, e.g.{" "}
            <span className="tabular text-foreground">15-08-26, 02-10-26</span>
          </p>
          <textarea
            className="mt-2 w-full border border-border px-3 py-2 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary"
            rows={2}
            value={blackoutDatesText}
            onChange={(e) => onBlackoutDatesChange(e.target.value)}
            onBlur={commitBlackoutDates}
            placeholder="15-08-26, 02-10-26"
            data-testid="blackout-dates-input"
          />
          {(prefs.blackout_dates || []).length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5" data-testid="blackout-dates-chips">
              {prefs.blackout_dates.map((iso) => (
                <span
                  key={iso}
                  className="px-2 py-0.5 border border-destructive text-destructive text-xs tabular"
                >
                  {formatDDMMYY(iso)}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="mt-6 border-t border-border pt-6">
          <Label className="overline">Weekend Boost</Label>
          <p className="text-xs text-muted-foreground mt-1">
            Multiplier applied to Sat & Sun slots. 1.0x = neutral · &lt;1 = fewer weekend spots · &gt;1 = more.
          </p>
          <div className="mt-3 grid grid-cols-12 gap-3 items-center" data-testid="weekend-boost-row">
            <div className="col-span-2 text-sm text-muted-foreground">Sat / Sun</div>
            <div className="col-span-8">
              <Slider
                value={[prefs.weekend_boost ?? 1]}
                min={0}
                max={3}
                step={0.1}
                onValueChange={(v) => setKey("weekend_boost", v[0])}
                data-testid="weekend-boost-slider"
              />
            </div>
            <div className="col-span-2 text-right tabular text-sm font-semibold">
              {(prefs.weekend_boost ?? 1).toFixed(1)}x
            </div>
          </div>
        </div>

        <div className="mt-6 border-t border-border pt-6">
          <div className="flex items-center justify-between">
            <Label className="overline">Reach ← → Frequency</Label>
            <span className="tabular text-xs text-muted-foreground">
              {(prefs.reach_vs_frequency ?? 0.5).toFixed(2)}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Left = spread spots across days (reach). Right = concentrate on same day (frequency).
          </p>
          <div className="mt-3">
            <Slider
              value={[prefs.reach_vs_frequency ?? 0.5]}
              min={0}
              max={1}
              step={0.05}
              onValueChange={(v) => setKey("reach_vs_frequency", v[0])}
              data-testid="reach-frequency-slider"
            />
            <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
              <span>Max reach</span>
              <span>Balanced</span>
              <span>Max frequency</span>
            </div>
          </div>
        </div>

        <div className="mt-6 border-t border-border pt-6">
          <Label className="overline">Movies Frequency Override</Label>
          <p className="text-xs text-muted-foreground mt-1">
            Spots on movie channels (genre contains &quot;MOV/Movie&quot;) use this frequency.
          </p>
          <div className="mt-2 flex items-center gap-3">
            <span className="text-sm text-muted-foreground">1 spot every</span>
            <Input
              type="number"
              min="15"
              step="15"
              value={prefs.movies_frequency_minutes ?? 60}
              onChange={(e) => setKey("movies_frequency_minutes", parseInt(e.target.value || 60))}
              className="w-24 tabular"
              data-testid="movies-frequency-input"
            />
            <span className="text-sm text-muted-foreground">minutes</span>
          </div>
        </div>
      </section>

      <div className="space-y-6">
        {/* -------- Channel spots/day (by genre) -------- */}
        <section className="bg-white border border-border p-8" data-testid="channel-spots-per-day-section">
          <div className="flex items-start justify-between">
            <div>
              <div className="overline mb-2">Average Spots per Day</div>
              <h2 className="font-display text-2xl font-extrabold tracking-tight">
                Daily rate by channel
              </h2>
              <p className="text-muted-foreground mt-2 text-sm">
                Punch in the target avg spots/day per channel. We auto-derive how many days
                each channel runs so it hits that rate.
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={clearAllChannelRates}
              data-testid="clear-channel-rates-button"
            >
              Clear all
            </Button>
          </div>

          <div className="mt-4 text-xs text-muted-foreground tabular">
            {filledChannels} of {totalChannels} channels configured
          </div>

          {genreChannels.length === 0 && (
            <div className="mt-6 p-4 border border-dashed border-border text-sm text-muted-foreground">
              No channels detected in the uploaded plan. Go back to Step 1 and upload a plan.
            </div>
          )}

          <div className="mt-4 space-y-4">
            {genreChannels.map(({ genre, channels }) => (
              <div key={genre} className="border border-border" data-testid={`genre-block-${genre.replace(/\s+/g, "-").toLowerCase()}`}>
                <div className="flex items-center justify-between bg-muted/50 px-4 py-2 border-b border-border">
                  <div className="flex items-center gap-3">
                    <span className="overline text-primary">{genre}</span>
                    <span className="text-xs text-muted-foreground tabular">
                      {channels.length} channel{channels.length !== 1 ? "s" : ""}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-muted-foreground">Apply to all:</span>
                    <Input
                      type="number"
                      min="0"
                      step="0.5"
                      placeholder="e.g. 8"
                      className="w-20 h-7 text-xs tabular"
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          applyToGenre(genre, channels, e.currentTarget.value);
                          e.currentTarget.value = "";
                        }
                      }}
                      onBlur={(e) => {
                        if (e.currentTarget.value) {
                          applyToGenre(genre, channels, e.currentTarget.value);
                          e.currentTarget.value = "";
                        }
                      }}
                      data-testid={`bulk-genre-${genre.replace(/\s+/g, "-").toLowerCase()}`}
                    />
                  </div>
                </div>
                <div className="divide-y divide-border">
                  {channels.map((ch) => (
                    <div key={ch} className="grid grid-cols-12 items-center px-4 py-2 gap-3">
                      <div className="col-span-8 text-sm truncate" title={ch}>
                        {ch}
                      </div>
                      <div className="col-span-4 flex items-center gap-2">
                        <Input
                          type="number"
                          min="0"
                          step="0.5"
                          value={spotsPerDayFor(ch)}
                          onChange={(e) => setSpotsPerDay(ch, e.target.value)}
                          placeholder="—"
                          className="w-20 tabular text-right h-8"
                          data-testid={`spd-input-${ch.replace(/[^a-z0-9]/gi, "-").toLowerCase()}`}
                        />
                        <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                          spots/day
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <p className="mt-4 text-[11px] text-muted-foreground">
            Blank = no daily-rate cap. The scheduler still respects the plan&apos;s total spots
            and the campaign start/end dates.
          </p>
        </section>

        {/* -------- Weekly GRP Dispersion -------- */}
        <section className="bg-white border border-border p-8">
          <div className="overline mb-2">Weekly GRP Dispersion</div>
          <h2 className="font-display text-2xl font-extrabold tracking-tight">
            Distribute weight across weeks
          </h2>
          <p className="text-muted-foreground mt-2 text-sm">
            Enter week-wise % that sums to 100. This drives both GRP and spot allocation.
          </p>

          <div className="mt-6 space-y-3" data-testid="weeks-list">
            {prefs.weekly_grp_dispersion.map((v, i) => (
              <div key={i} className="grid grid-cols-6 items-center gap-3">
                <Label className="col-span-2 text-sm">Week {i + 1}</Label>
                <div className="col-span-3 h-2 bg-muted overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all"
                    style={{ width: `${Math.min(100, Number(v) || 0)}%` }}
                  />
                </div>
                <div className="col-span-1 relative">
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    value={v}
                    onChange={(e) => setWeek(i, e.target.value)}
                    className="tabular pr-6 text-right"
                    data-testid={`week-input-${i}`}
                  />
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                    %
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
            <span className="text-sm text-muted-foreground">Total</span>
            <span
              className={`font-display font-bold text-xl tabular ${
                Math.abs(weeklyTotal - 100) < 0.5 ? "text-primary" : "text-destructive"
              }`}
              data-testid="weekly-total"
            >
              {weeklyTotal.toFixed(1)}%
            </span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                const base = 100 / weeks;
                setKey(
                  "weekly_grp_dispersion",
                  Array.from({ length: weeks }, () => Number(base.toFixed(2)))
                );
              }}
              data-testid="reset-weekly-button"
            >
              Uniform
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                const raw = Array.from({ length: weeks }, (_, i) => weeks - i);
                const s = raw.reduce((a, b) => a + b, 0);
                setKey(
                  "weekly_grp_dispersion",
                  raw.map((r) => Number(((r * 100) / s).toFixed(2)))
                );
              }}
              data-testid="frontload-weekly-button"
            >
              Front-load
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                const mid = (weeks - 1) / 2;
                const raw = Array.from({ length: weeks }, (_, i) => {
                  const d = i - mid;
                  return Math.exp(-(d * d) / (2 * Math.pow(weeks / 3.5, 2)));
                });
                const s = raw.reduce((a, b) => a + b, 0);
                setKey(
                  "weekly_grp_dispersion",
                  raw.map((r) => Number(((r * 100) / s).toFixed(2)))
                );
              }}
              data-testid="bell-weekly-button"
            >
              Bell curve
            </Button>
          </div>
        </section>
      </div>
    </div>
  );
}
