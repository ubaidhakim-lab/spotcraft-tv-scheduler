import { useRef, useState } from "react";
import { UploadCloud, FileSpreadsheet, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function StepUpload({ onUpload, loading, upload }) {
  const inputRef = useRef(null);
  const [drag, setDrag] = useState(false);

  const handleFile = (file) => {
    if (!file) return;
    const ok = /\.(xlsx|xls|csv)$/i.test(file.name);
    if (!ok) return;
    onUpload(file);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 bg-white border border-border p-8">
        <div className="overline mb-2">Step 1 · Upload Media Plan</div>
        <h2 className="font-display text-3xl font-extrabold tracking-tight">Load your ACD plan</h2>
        <p className="text-muted-foreground mt-2 text-sm max-w-lg">
          Upload the master plan spreadsheet. We map columns like Market, Genre, Channel, Program,
          Days, Start/End Time, ACD, FCT, GRP, Outlay automatically.
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
            "Net Rate/10sec",
            "ACD (secs)",
            "Spots",
            "FCT (secs)",
            "Outlay",
            "Log TVR",
            "GRP",
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
          </div>
        )}
      </aside>
    </div>
  );
}
