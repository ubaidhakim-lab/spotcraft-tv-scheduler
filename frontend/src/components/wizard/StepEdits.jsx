import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function StepEdits({ upload, edits, setEdits }) {
  const total = edits.reduce((a, e) => a + Number(e.percentage || 0), 0);
  const totalFct = upload.summary?.total_fct || 0;

  const update = (i, key, val) => {
    const copy = [...edits];
    copy[i] = { ...copy[i], [key]: key === "duration" ? parseInt(val || 0) : parseFloat(val || 0) };
    setEdits(copy);
  };

  const addEdit = () => setEdits([...edits, { duration: 15, percentage: 0 }]);
  const removeEdit = (i) => setEdits(edits.filter((_, idx) => idx !== i));

  const presets = [
    { name: "60/30/10", vals: [{ duration: 30, percentage: 60 }, { duration: 20, percentage: 30 }, { duration: 10, percentage: 10 }] },
    { name: "50/30/20", vals: [{ duration: 30, percentage: 50 }, { duration: 20, percentage: 30 }, { duration: 10, percentage: 20 }] },
    { name: "70/30 (30s+15s)", vals: [{ duration: 30, percentage: 70 }, { duration: 15, percentage: 30 }] },
    { name: "100% 30s", vals: [{ duration: 30, percentage: 100 }] },
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 bg-white border border-border p-8">
        <div className="overline mb-2">Step 2 · Edit-wise Dispersion</div>
        <h2 className="font-display text-3xl font-extrabold tracking-tight">
          How should FCT split across edits?
        </h2>
        <p className="text-muted-foreground mt-2 text-sm max-w-xl">
          Enter the copy-length mix. Total FCT of{" "}
          <span className="text-foreground font-semibold tabular-nums">
            {totalFct.toLocaleString()} sec
          </span>{" "}
          will be dispersed across these edits, then converted to spots.
        </p>

        <div className="mt-6 flex flex-wrap gap-2" data-testid="preset-group">
          {presets.map((p) => (
            <Button
              key={p.name}
              variant="outline"
              size="sm"
              onClick={() => setEdits(p.vals)}
              data-testid={`preset-${p.name.replace(/[^a-z0-9]/gi, "-").toLowerCase()}`}
            >
              {p.name}
            </Button>
          ))}
        </div>

        <div className="mt-6 space-y-3" data-testid="edits-list">
          {edits.map((e, i) => {
            const fct = totalFct * (Number(e.percentage) || 0) / 100;
            const spots = e.duration > 0 ? fct / e.duration : 0;
            return (
              <div
                key={i}
                className="grid grid-cols-12 gap-3 items-end border border-border p-4"
                data-testid={`edit-row-${i}`}
              >
                <div className="col-span-3">
                  <Label className="overline">Duration (sec)</Label>
                  <Input
                    type="number"
                    min="1"
                    value={e.duration}
                    onChange={(ev) => update(i, "duration", ev.target.value)}
                    className="mt-1 tabular"
                    data-testid={`edit-duration-${i}`}
                  />
                </div>
                <div className="col-span-3">
                  <Label className="overline">Percentage</Label>
                  <div className="relative mt-1">
                    <Input
                      type="number"
                      min="0"
                      max="100"
                      value={e.percentage}
                      onChange={(ev) => update(i, "percentage", ev.target.value)}
                      className="pr-8 tabular"
                      data-testid={`edit-percentage-${i}`}
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">
                      %
                    </span>
                  </div>
                </div>
                <div className="col-span-3">
                  <Label className="overline">FCT (calculated)</Label>
                  <div className="h-9 flex items-center px-3 border border-border bg-muted/40 mt-1 text-sm tabular">
                    {fct.toLocaleString(undefined, { maximumFractionDigits: 1 })} sec
                  </div>
                </div>
                <div className="col-span-2">
                  <Label className="overline">Spots</Label>
                  <div className="h-9 flex items-center px-3 border border-border bg-muted/40 mt-1 text-sm tabular">
                    {Math.round(spots)}
                  </div>
                </div>
                <div className="col-span-1 flex justify-end">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removeEdit(i)}
                    disabled={edits.length <= 1}
                    data-testid={`remove-edit-${i}`}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>

        <Button
          variant="outline"
          className="mt-4"
          onClick={addEdit}
          data-testid="add-edit-button"
        >
          <Plus className="h-4 w-4 mr-2" /> Add Edit
        </Button>
      </div>

      <aside className="bg-white border border-border p-6">
        <div className="overline mb-3">Validation</div>
        <div className="text-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Total percentage</span>
            <span
              className={`font-display font-bold text-xl tabular ${
                Math.abs(total - 100) < 0.5 ? "text-primary" : "text-destructive"
              }`}
              data-testid="total-percentage"
            >
              {total.toFixed(1)}%
            </span>
          </div>
          <div className="h-2 bg-muted overflow-hidden">
            <div
              className={`h-full transition-all ${
                Math.abs(total - 100) < 0.5 ? "bg-primary" : "bg-destructive"
              }`}
              style={{ width: `${Math.min(100, total)}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Percentages must sum to 100 before generating.
          </p>
        </div>

        <div className="border-t border-border mt-6 pt-4">
          <div className="overline mb-3">Plan Summary</div>
          <dl className="text-sm space-y-2">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Rows</dt>
              <dd className="tabular">{upload.row_count}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Total FCT</dt>
              <dd className="tabular">{(upload.summary?.total_fct || 0).toLocaleString()}s</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Total Spots</dt>
              <dd className="tabular">{(upload.summary?.total_spots || 0).toLocaleString()}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Total GRP</dt>
              <dd className="tabular">{(upload.summary?.total_grp || 0).toLocaleString(undefined, {maximumFractionDigits:2})}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Total Outlay</dt>
              <dd className="tabular">{(upload.summary?.total_outlay || 0).toLocaleString()}</dd>
            </div>
          </dl>
        </div>
      </aside>
    </div>
  );
}
