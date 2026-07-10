import { useState, useEffect } from "react";
import { toast } from "sonner";
import {
  uploadPlan,
  learnSample,
  generatePlan,
  downloadUrl,
  saveSession,
  listSessions,
  getSession,
  deleteSession,
} from "@/lib/api";
import WizardHeader from "@/components/wizard/WizardHeader";
import StepUpload from "@/components/wizard/StepUpload";
import StepEdits from "@/components/wizard/StepEdits";
import StepPrefs from "@/components/wizard/StepPrefs";
import StepResults from "@/components/wizard/StepResults";
import SessionsDialog from "@/components/SessionsDialog";
import { Button } from "@/components/ui/button";
import { ArrowLeft, ArrowRight, RefreshCcw, FolderOpen, Save } from "lucide-react";

const STEPS = [
  { id: 1, key: "upload", label: "Upload Plan" },
  { id: 2, key: "edits", label: "Edit Dispersion" },
  { id: 3, key: "prefs", label: "Scheduling" },
  { id: 4, key: "results", label: "Review & Export" },
];

const DEFAULT_PREFS = {
  campaign_start: new Date().toISOString().slice(0, 10),
  campaign_end: new Date(Date.now() + 6 * 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
  campaign_weeks: 6,
  spot_frequency_minutes: 30,
  gec_genres: ["GEC"],
  gec_planning_weeks: null,
  weekly_grp_dispersion: [20, 20, 18, 15, 15, 12],
  blackout_days: [],
  blackout_dates: [],
  daypart_weights: [],
};

export default function PlanBuilder() {
  const [step, setStep] = useState(1);
  const [upload, setUpload] = useState(null);
  const [edits, setEdits] = useState([
    { duration: 30, percentage: 60 },
    { duration: 20, percentage: 30 },
    { duration: 10, percentage: 10 },
  ]);
  const [rowOverrides, setRowOverrides] = useState({}); // { row_id: [edits] }
  const [prefs, setPrefs] = useState(DEFAULT_PREFS);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const [sessions, setSessions] = useState([]);

  useEffect(() => {
    listSessions().then(setSessions).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onUpload = async (file) => {
    setLoading(true);
    try {
      const data = await uploadPlan(file);
      setUpload(data);
      toast.success(`Loaded ${data.row_count} rows from ${data.filename}`);
      setStep(2);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const onLearn = async (file) => {
    setLoading(true);
    try {
      const data = await learnSample(file);
      if (data.edits && data.edits.length > 0) {
        setEdits(data.edits);
      }
      const patch = {};
      if (data.weekly_grp_dispersion?.length > 0) {
        patch.weekly_grp_dispersion = data.weekly_grp_dispersion;
        patch.campaign_weeks = data.weekly_grp_dispersion.length;
      }
      if (Object.keys(patch).length) setPrefs((p) => ({ ...p, ...patch }));
      toast.success(
        `Learned ${data.edits.length} edit(s) & ${data.weekly_grp_dispersion.length} week weightings from ${data.source_filename}`
      );
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to learn from sample");
    } finally {
      setLoading(false);
    }
  };

  const onGenerate = async () => {
    const sum = edits.reduce((a, e) => a + Number(e.percentage || 0), 0);
    if (Math.abs(sum - 100) > 0.5) {
      toast.error(`Edit % must sum to 100 (currently ${sum.toFixed(1)})`);
      return;
    }
    setLoading(true);
    try {
      const overrides = Object.entries(rowOverrides).map(([rid, es]) => ({
        row_id: Number(rid),
        edits: es,
      }));
      const data = await generatePlan(upload.plan_id, edits, prefs, overrides);
      setResult(data);
      toast.success("Plan generated");
      setStep(4);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Generation failed");
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setStep(1);
    setUpload(null);
    setResult(null);
    setRowOverrides({});
    setPrefs(DEFAULT_PREFS);
  };

  const doSaveSession = async () => {
    if (!upload) {
      toast.error("Upload a plan first");
      return;
    }
    const name = window.prompt(
      "Session name:",
      `${upload.metadata?.Campaign || upload.filename} - ${new Date().toLocaleDateString()}`
    );
    if (!name) return;
    try {
      const overrides = Object.entries(rowOverrides).map(([rid, es]) => ({
        row_id: Number(rid),
        edits: es,
      }));
      await saveSession({
        name,
        plan_id: upload.plan_id,
        edits,
        row_overrides: overrides,
        prefs,
      });
      const items = await listSessions();
      setSessions(items);
      toast.success("Session saved");
    } catch (e) {
      toast.error("Failed to save session");
    }
  };

  const loadSession = async (id) => {
    try {
      const s = await getSession(id);
      setEdits(s.edits);
      setPrefs(s.prefs);
      const map = {};
      (s.row_overrides || []).forEach((ov) => {
        map[ov.row_id] = ov.edits;
      });
      setRowOverrides(map);
      // reload the plan
      const planRes = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/plans/${s.plan_id}`);
      if (planRes.ok) {
        const plan = await planRes.json();
        setUpload({
          plan_id: plan.id,
          filename: plan.filename,
          metadata: plan.metadata,
          columns: plan.columns,
          row_count: plan.parsed_rows.length,
          rows: plan.parsed_rows,
          summary: {
            total_fct: plan.parsed_rows.reduce((a, r) => a + (r.fct || 0), 0),
            total_spots: plan.parsed_rows.reduce((a, r) => a + (r.spots || 0), 0),
            total_grp: plan.parsed_rows.reduce((a, r) => a + (r.grp || 0), 0),
            total_outlay: plan.parsed_rows.reduce((a, r) => a + (r.outlay || 0), 0),
          },
        });
      }
      setSessionsOpen(false);
      setStep(2);
      toast.success(`Loaded session: ${s.name}`);
    } catch {
      toast.error("Failed to load session");
    }
  };

  const removeSession = async (id) => {
    await deleteSession(id);
    const items = await listSessions();
    setSessions(items);
  };

  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-white sticky top-0 z-40">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="h-8 w-8 bg-primary flex items-center justify-center text-white font-display font-bold"
              data-testid="app-logo"
            >
              A
            </div>
            <div>
              <div className="font-display text-lg font-bold tracking-tight">ACD Plan Builder</div>
              <div className="overline text-[10px]">Edit-wise Dispersion & Day-wise Scheduling</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setSessionsOpen(true)} data-testid="sessions-open-button">
              <FolderOpen className="h-4 w-4 mr-2" /> Sessions ({sessions.length})
            </Button>
            <Button variant="outline" size="sm" onClick={doSaveSession} data-testid="save-session-button">
              <Save className="h-4 w-4 mr-2" /> Save
            </Button>
            <Button variant="ghost" size="sm" onClick={reset} data-testid="reset-button">
              <RefreshCcw className="h-4 w-4 mr-2" /> Start Over
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-6 py-8">
        <WizardHeader steps={STEPS} current={step} />

        <section className="mt-8 fade-up" key={step}>
          {step === 1 && (
            <StepUpload onUpload={onUpload} onLearn={onLearn} loading={loading} upload={upload} />
          )}
          {step === 2 && upload && (
            <StepEdits
              upload={upload}
              edits={edits}
              setEdits={setEdits}
              rowOverrides={rowOverrides}
              setRowOverrides={setRowOverrides}
            />
          )}
          {step === 3 && upload && (
            <StepPrefs prefs={prefs} setPrefs={setPrefs} upload={upload} onLearn={onLearn} />
          )}
          {step === 4 && result && (
            <StepResults result={result} downloadHref={downloadUrl(result.result_id)} />
          )}
        </section>

        <div className="mt-10 flex items-center justify-between pb-24">
          <Button
            variant="outline"
            onClick={() => setStep((s) => Math.max(1, s - 1))}
            disabled={step === 1}
            data-testid="back-button"
          >
            <ArrowLeft className="h-4 w-4 mr-2" /> Back
          </Button>

          {step === 2 && (
            <Button onClick={() => setStep(3)} data-testid="next-to-prefs-button">
              Continue <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          )}
          {step === 3 && (
            <Button onClick={onGenerate} disabled={loading} data-testid="generate-button">
              {loading ? "Generating..." : "Generate Plan"} <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          )}
          {step === 4 && (
            <Button onClick={reset} data-testid="new-plan-button">
              Start New Plan
            </Button>
          )}
        </div>
      </main>

      <SessionsDialog
        open={sessionsOpen}
        onClose={() => setSessionsOpen(false)}
        sessions={sessions}
        onLoad={loadSession}
        onDelete={removeSession}
      />
    </div>
  );
}
