import { useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DAYPARTS = [
  "Morning",
  "Late Morning",
  "Afternoon",
  "Late Afternoon",
  "Prime Time",
  "Late Prime",
  "Overnight",
];

export default function StepPrefs({ prefs, setPrefs, upload }) {
  const setKey = (k, v) => setPrefs({ ...prefs, [k]: v });

  const weeks = Math.max(1, prefs.campaign_weeks || 1);

  useEffect(() => {
    if (prefs.weekly_grp_dispersion.length !== weeks) {
      const base = 100 / weeks;
      setPrefs({
        ...prefs,
        weekly_grp_dispersion: Array.from({ length: weeks }, () => Number(base.toFixed(2))),
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weeks]);

  const setWeek = (i, val) => {
    const arr = [...prefs.weekly_grp_dispersion];
    arr[i] = parseFloat(val || 0);
    setKey("weekly_grp_dispersion", arr);
  };

  const toggleBlackout = (d) => {
    const has = prefs.blackout_days.includes(d);
    setKey(
      "blackout_days",
      has ? prefs.blackout_days.filter((x) => x !== d) : [...prefs.blackout_days, d]
    );
  };

  const gecOnly = !!prefs.gec_planning_weeks;
  const weeklyTotal = prefs.weekly_grp_dispersion.reduce((a, b) => a + Number(b || 0), 0);

  const weightOf = (dp) => {
    const w = prefs.daypart_weights.find((x) => x.daypart === dp);
    return w ? w.weight : 1;
  };
  const setWeight = (dp, val) => {
    const others = prefs.daypart_weights.filter((x) => x.daypart !== dp);
    setKey("daypart_weights", [...others, { daypart: dp, weight: val }]);
  };
  const resetDayparts = () => setKey("daypart_weights", []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <section className="bg-white border border-border p-8">
        <div className="overline mb-2">Step 3 · Scheduling Preferences</div>
        <h2 className="font-display text-3xl font-extrabold tracking-tight">
          Campaign & pacing
        </h2>
        <p className="text-muted-foreground mt-2 text-sm">
          Answer a few questions and we'll schedule the day-wise spots.
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
            <Label className="overline">Duration (weeks)</Label>
            <Input
              type="number"
              min="1"
              max="52"
              value={prefs.campaign_weeks}
              onChange={(e) => setKey("campaign_weeks", parseInt(e.target.value || 1))}
              className="mt-1 tabular"
              data-testid="campaign-weeks-input"
            />
          </div>
        </div>

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
          <Label className="overline">Blackout days</Label>
          <p className="text-xs text-muted-foreground mt-1">
            No spots will be scheduled on selected days
          </p>
          <div className="mt-3 flex flex-wrap gap-2" data-testid="blackout-days">
            {DAYS.map((d) => {
              const active = prefs.blackout_days.includes(d);
              return (
                <button
                  key={d}
                  type="button"
                  onClick={() => toggleBlackout(d)}
                  className={`px-3 py-1.5 border text-sm transition-colors ${
                    active
                      ? "border-destructive bg-destructive text-white"
                      : "border-border hover:border-primary"
                  }`}
                  data-testid={`blackout-${d.toLowerCase()}`}
                >
                  {d}
                </button>
              );
            })}
          </div>
        </div>

        <div className="mt-6 border-t border-border pt-6">
          <div className="flex items-center justify-between">
            <div>
              <Label className="overline">Daypart Weighting</Label>
              <p className="text-xs text-muted-foreground mt-1">
                Bias slot selection toward specific dayparts (higher = more spots)
              </p>
            </div>
            <Button variant="ghost" size="sm" onClick={resetDayparts} data-testid="reset-dayparts">
              Reset
            </Button>
          </div>
          <div className="mt-4 space-y-3" data-testid="daypart-weights">
            {DAYPARTS.map((dp) => {
              const w = weightOf(dp);
              return (
                <div key={dp} className="grid grid-cols-12 gap-3 items-center">
                  <div className="col-span-4 text-sm">{dp}</div>
                  <div className="col-span-6">
                    <Slider
                      value={[w]}
                      min={0}
                      max={3}
                      step={0.1}
                      onValueChange={(v) => setWeight(dp, v[0])}
                      data-testid={`weight-slider-${dp.replace(/\s+/g, "-").toLowerCase()}`}
                    />
                  </div>
                  <div className="col-span-2 text-right tabular text-sm font-semibold">
                    {w.toFixed(1)}x
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

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
              // Frontload: descending
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
              // Bell curve
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
  );
}
