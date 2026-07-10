import { useState } from "react";
import { toast } from "sonner";
import { uploadPlan, generatePlan, downloadUrl } from "@/lib/api";
import WizardHeader from "@/components/wizard/WizardHeader";
import StepUpload from "@/components/wizard/StepUpload";
import StepEdits from "@/components/wizard/StepEdits";
import StepPrefs from "@/components/wizard/StepPrefs";
import StepResults from "@/components/wizard/StepResults";
import { Button } from "@/components/ui/button";
import { ArrowLeft, ArrowRight, RefreshCcw } from "lucide-react";

const STEPS = [
  { id: 1, key: "upload", label: "Upload Plan" },
  { id: 2, key: "edits", label: "Edit Dispersion" },
  { id: 3, key: "prefs", label: "Scheduling" },
  { id: 4, key: "results", label: "Review & Export" },
];

export default function PlanBuilder() {
  const [step, setStep] = useState(1);
  const [upload, setUpload] = useState(null);
  const [edits, setEdits] = useState([
    { duration: 30, percentage: 60 },
    { duration: 20, percentage: 30 },
    { duration: 10, percentage: 10 },
  ]);
  const [prefs, setPrefs] = useState({
    campaign_start: new Date().toISOString().slice(0, 10),
    campaign_weeks: 4,
    spot_frequency_minutes: 30,
    gec_genres: ["GEC"],
    gec_planning_weeks: null,
    weekly_grp_dispersion: [30, 30, 25, 15],
    blackout_days: [],
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

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

  const onGenerate = async () => {
    const sum = edits.reduce((a, e) => a + Number(e.percentage || 0), 0);
    if (Math.abs(sum - 100) > 0.5) {
      toast.error(`Edit % must sum to 100 (currently ${sum})`);
      return;
    }
    setLoading(true);
    try {
      const data = await generatePlan(upload.plan_id, edits, prefs);
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
  };

  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-white">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 bg-primary flex items-center justify-center text-white font-display font-bold" data-testid="app-logo">
              A
            </div>
            <div>
              <div className="font-display text-lg font-bold tracking-tight">ACD Plan Builder</div>
              <div className="overline text-[10px]">Edit-wise Dispersion & Day-wise Scheduling</div>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={reset} data-testid="reset-button">
            <RefreshCcw className="h-4 w-4 mr-2" /> Start Over
          </Button>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-6 py-8">
        <WizardHeader steps={STEPS} current={step} />

        <section className="mt-8 fade-up" key={step}>
          {step === 1 && <StepUpload onUpload={onUpload} loading={loading} upload={upload} />}
          {step === 2 && upload && (
            <StepEdits upload={upload} edits={edits} setEdits={setEdits} />
          )}
          {step === 3 && upload && (
            <StepPrefs prefs={prefs} setPrefs={setPrefs} upload={upload} />
          )}
          {step === 4 && result && (
            <StepResults
              result={result}
              downloadHref={downloadUrl(result.result_id)}
            />
          )}
        </section>

        <div className="mt-10 flex items-center justify-between">
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
    </div>
  );
}
