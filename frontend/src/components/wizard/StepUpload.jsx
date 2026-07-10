import { useRef, useState } from "react";
import { UploadCloud, FileSpreadsheet, CheckCircle2, Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function StepUpload({ onUpload, onLearn, loading, upload }) {
  const inputRef = useRef(null);
  const learnRef = useRef(null);
  const [drag, setDrag] = useState(false);
  const [learned, setLearned] = useState(null);

  const handleFile = (file) => {
    if (!file) return;
    const ok = /\.(xlsx|xls|csv)$/i.test(file.name);
    if (!ok) return;
    onUpload(file);
  };

  const handleLearn = async (file) => {
    if (!file) return;
    setLearned({ name: file.name, ok: false });
    await onLearn(file);
    setLearned({ name: file.name, ok: true });
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 bg-white border border-border p-8">
        <div className="overline mb-2">Step 1 · Upload Media Plan</div>
        <h2 className="font-display text-3xl font-extrabold tracking-tight">Load your ACD plan</h2>
        <p className="text-muted-foreground mt-2 text-sm max-w-lg">
          Upload the master plan spreadsheet. We handle multi-row headers, auto-detect columns
          (Nett Rate/10sec, ACD, FCT, GRP, Net Outlay, etc.), and preserve the layout on export.
        </p>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            handleFile(e.dataTransfer.files?.[0]);
          }}
          className={`mt-8 border-2 border-dashed p-12 text-center transition-colors ${
            drag ? "border-primary bg-primary/5" : "border-border bg-muted/30"
          }`}
          data-testid="upload-dropzone"
        >
          <UploadCloud className="h-10 w-10 mx-auto text-primary" />
          <div className="mt-4 font-display font-semibold text-lg">
            Drop your plan file here
          </div>
          <div className="text-sm text-muted-foreground mt-1">
            Supports .xlsx, .xls, .csv up to 20MB
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            className="hidden"
            data-testid="file-input"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          <Button
            className="mt-6"
            onClick={() => inputRef.current?.click()}
            disabled={loading}
            data-testid="browse-file-button"
          >
            {loading ? "Uploading..." : "Browse files"}
          </Button>
        </div>

        <div className="mt-6 border border-dashed border-border p-5 bg-muted/20">
          <div className="flex items-start gap-3">
            <Wand2 className="h-5 w-5 text-primary mt-0.5" />
            <div className="flex-1">
              <div className="font-semibold text-sm">Learn from a past schedule</div>
              <p className="text-xs text-muted-foreground mt-1 max-w-md">
                Optional: upload a previous "Editwise plan & Schedule" file. We'll extract the
                edit dispersion (durations & %) and weekly dispersion pattern to prefill the wizard.
              </p>
            </div>
            <input
              ref={learnRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              className="hidden"
              data-testid="learn-file-input"
              onChange={(e) => handleLearn(e.target.files?.[0])}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => learnRef.current?.click()}
              disabled={loading}
              data-testid="learn-button"
            >
              Choose sample
            </Button>
          </div>
          {learned && (
            <div className="mt-3 text-xs text-primary flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" /> Learned from {learned.name}
            </div>
          )}
        </div>
      </div>

      <aside className="bg-white border border-border p-6">
        <div className="overline mb-3">Expected Columns</div>
        <ul className="text-sm space-y-2 text-muted-foreground">
          {[
            "Market",
            "Genre",
            "Channel",
            "Program",
            "Days",
            "Start Time / End Time",
            "Nett Rate/10sec",
            "ACD (secs)",
            "Spots",
            "FCT (secs)",
            "Net Outlay",
            "Log TVR",
            "GRP",
            "NGRP · CPRP",
          ].map((c) => (
            <li key={c} className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 bg-primary" /> {c}
            </li>
          ))}
        </ul>
        {upload && (
          <div className="mt-6 border-t border-border pt-4" data-testid="upload-summary">
            <div className="flex items-center gap-2 text-primary">
              <CheckCircle2 className="h-5 w-5" />
              <span className="font-semibold">Loaded</span>
            </div>
            <div className="flex items-center gap-2 mt-2 text-sm">
              <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />
              <span className="truncate">{upload.filename}</span>
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {upload.row_count} rows · {upload.columns.length} columns
            </div>
            {upload.metadata && Object.keys(upload.metadata).length > 0 && (
              <dl className="mt-4 text-xs space-y-1">
                {Object.entries(upload.metadata).map(([k, v]) => (
                  <div key={k} className="grid grid-cols-2 gap-2">
                    <dt className="text-muted-foreground">{k}</dt>
                    <dd className="truncate">{String(v)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}
