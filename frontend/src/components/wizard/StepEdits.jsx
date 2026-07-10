import { useState } from "react";
import { Plus, Trash2, Sliders } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

const PRESETS = [
  { name: "60-30-10", vals: [{ duration: 30, percentage: 60 }, { duration: 20, percentage: 30 }, { duration: 10, percentage: 10 }] },
  { name: "50-30-20", vals: [{ duration: 30, percentage: 50 }, { duration: 20, percentage: 30 }, { duration: 10, percentage: 20 }] },
  { name: "45-30-20-10", vals: [{ duration: 45, percentage: 10 }, { duration: 30, percentage: 40 }, { duration: 20, percentage: 30 }, { duration: 10, percentage: 20 }] },
  { name: "70-30 (30s+15s)", vals: [{ duration: 30, percentage: 70 }, { duration: 15, percentage: 30 }] },
  { name: "100% 30s", vals: [{ duration: 30, percentage: 100 }] },
];

function EditsEditor({ edits, setEdits, totalFct, showPresets = true }) {
  const total = edits.reduce((a, e) => a + Number(e.percentage || 0), 0);

  const update = (i, key, val) => {
    const copy = [...edits];
    copy[i] = {
      ...copy[i],
      [key]: key === "duration" ? parseInt(val || 0) : parseFloat(val || 0),
    };
    setEdits(copy);
  };
  const addEdit = () => setEdits([...edits, { duration: 15, percentage: 0 }]);
  const removeEdit = (i) => setEdits(edits.filter((_, idx) => idx !== i));

  return (
    <div>
      {showPresets && (
        <div className="flex flex-wrap gap-2" data-testid="preset-group">
          {PRESETS.map((p) => (
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
      )}

      <div className="mt-4 space-y-2" data-testid="edits-list">
        {edits.map((e, i) => {
          const fct = (Number(totalFct) || 0) * (Number(e.percentage) || 0) / 100;
          const spots = e.duration > 0 ? fct / e.duration : 0;
          return (
            <div
              key={i}
              className="grid grid-cols-12 gap-2 items-end border border-border p-3"
              data-testid={`edit-row-${i}`}
            >
              <div className="col-span-3">
                <Label className="overline">Duration (s)</Label>
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
                <Label className="overline">%</Label>
                <div className="relative mt-1">
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    value={e.percentage}
                    onChange={(ev) => update(i, "percentage", ev.target.value)}
                    className="pr-7 tabular"
                    data-testid={`edit-percentage-${i}`}
                  />
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground text-xs">
                    %
                  </span>
                </div>
              </div>
              <div className="col-span-3">
                <Label className="overline">FCT</Label>
                <div className="h-9 flex items-center px-3 border border-border bg-muted/40 mt-1 text-xs tabular">
                  {fct.toLocaleString(undefined, { maximumFractionDigits: 1 })}s
                </div>
              </div>
              <div className="col-span-2">
                <Label className="overline">Spots</Label>
                <div className="h-9 flex items-center px-3 border border-border bg-muted/40 mt-1 text-xs tabular">
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

      <div className="mt-3 flex items-center justify-between">
        <Button variant="outline" size="sm" onClick={addEdit} data-testid="add-edit-button">
          <Plus className="h-4 w-4 mr-2" /> Add Edit
        </Button>
        <div className="text-sm">
          Total:{" "}
          <span
            className={`font-display font-bold text-lg tabular ${
              Math.abs(total - 100) < 0.5 ? "text-primary" : "text-destructive"
            }`}
            data-testid="total-percentage"
          >
            {total.toFixed(1)}%
          </span>
        </div>
      </div>
    </div>
  );
}

export default function StepEdits({ upload, edits, setEdits, rowOverrides, setRowOverrides }) {
  const total = edits.reduce((a, e) => a + Number(e.percentage || 0), 0);
  const totalFct = upload.summary?.total_fct || 0;
  const [overrideRow, setOverrideRow] = useState(null); // row object being edited
  const [overrideEdits, setOverrideEdits] = useState([]);

  const openOverride = (row) => {
    setOverrideRow(row);
    setOverrideEdits(rowOverrides[row._row_id] || JSON.parse(JSON.stringify(edits)));
  };
  const saveOverride = () => {
    const s = overrideEdits.reduce((a, e) => a + Number(e.percentage || 0), 0);
    if (Math.abs(s - 100) > 0.5) {
      alert(`Percentages must sum to 100 (currently ${s.toFixed(1)})`);
      return;
    }
    setRowOverrides({ ...rowOverrides, [overrideRow._row_id]: overrideEdits });
    setOverrideRow(null);
  };
  const removeOverride = (rid) => {
    const copy = { ...rowOverrides };
    delete copy[rid];
    setRowOverrides(copy);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 bg-white border border-border p-8">
        <div className="overline mb-2">Step 2 · Edit-wise Dispersion</div>
        <h2 className="font-display text-3xl font-extrabold tracking-tight">
          How should FCT split across edits?
        </h2>
        <p className="text-muted-foreground mt-2 text-sm max-w-xl">
          Set the global copy-length mix. Total plan FCT of{" "}
          <span className="text-foreground font-semibold tabular-nums">
            {totalFct.toLocaleString()} sec
          </span>{" "}
          will be dispersed by these percentages, then converted to spots.
          Override per program below if needed.
        </p>

        <div className="mt-6">
          <EditsEditor edits={edits} setEdits={setEdits} totalFct={totalFct} />
        </div>

        <div className="mt-8 border-t border-border pt-6">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="overline">Per-program overrides</div>
              <p className="text-xs text-muted-foreground mt-1">
                Optionally use a different edit mix for specific programs.
              </p>
            </div>
            <div className="text-xs text-muted-foreground">
              {Object.keys(rowOverrides).length} override(s)
            </div>
          </div>

          <div className="border border-border max-h-80 overflow-auto" data-testid="rows-list">
            <table className="data-table w-full">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th>Channel</th>
                  <th>Program</th>
                  <th>Days</th>
                  <th className="num">Spots</th>
                  <th className="num">FCT</th>
                  <th>Mix</th>
                  <th style={{ width: 100 }}></th>
                </tr>
              </thead>
              <tbody>
                {upload.rows.slice(0, 200).map((r) => {
                  const ov = rowOverrides[r._row_id];
                  return (
                    <tr key={r._row_id} data-testid={`row-${r._row_id}`}>
                      <td className="num text-muted-foreground">{r._row_id + 1}</td>
                      <td className="font-semibold">{r.channel}</td>
                      <td>{r.program}</td>
                      <td className="text-xs text-muted-foreground">{r.days}</td>
                      <td className="num">{Math.round(r.spots || 0)}</td>
                      <td className="num">{Math.round(r.fct || 0)}</td>
                      <td className="text-xs">
                        {ov ? (
                          <span className="text-primary font-semibold">
                            {ov.map((e) => `${e.duration}s(${e.percentage}%)`).join(" · ")}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">global</span>
                        )}
                      </td>
                      <td>
                        <div className="flex gap-1 justify-end">
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 text-xs"
                            onClick={() => openOverride(r)}
                            data-testid={`override-${r._row_id}`}
                          >
                            <Sliders className="h-3 w-3 mr-1" /> Edit
                          </Button>
                          {ov && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 w-7 p-0"
                              onClick={() => removeOverride(r._row_id)}
                              data-testid={`clear-override-${r._row_id}`}
                            >
                              <Trash2 className="h-3 w-3 text-destructive" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <aside className="bg-white border border-border p-6">
        <div className="overline mb-3">Validation</div>
        <div className="text-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Global total</span>
            <span
              className={`font-display font-bold text-2xl tabular ${
                Math.abs(total - 100) < 0.5 ? "text-primary" : "text-destructive"
              }`}
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
              <dd className="tabular">
                {(upload.summary?.total_spots || 0).toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Total GRP</dt>
              <dd className="tabular">
                {(upload.summary?.total_grp || 0).toLocaleString(undefined, {
                  maximumFractionDigits: 2,
                })}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Total Outlay</dt>
              <dd className="tabular">
                {(upload.summary?.total_outlay || 0).toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })}
              </dd>
            </div>
          </dl>
        </div>
      </aside>

      <Dialog open={!!overrideRow} onOpenChange={(v) => !v && setOverrideRow(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle className="font-display tracking-tight">
              Override edit mix
            </DialogTitle>
          </DialogHeader>
          {overrideRow && (
            <div>
              <div className="border border-border p-3 bg-muted/30 text-sm space-y-1">
                <div className="font-semibold">
                  {overrideRow.channel} · {overrideRow.program}
                </div>
                <div className="text-xs text-muted-foreground">
                  Days: {overrideRow.days} · FCT: {Math.round(overrideRow.fct || 0)}s · Spots:{" "}
                  {Math.round(overrideRow.spots || 0)}
                </div>
              </div>
              <div className="mt-4">
                <EditsEditor
                  edits={overrideEdits}
                  setEdits={setOverrideEdits}
                  totalFct={overrideRow.fct || 0}
                  showPresets={false}
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setOverrideRow(null)} data-testid="override-cancel">
              Cancel
            </Button>
            <Button onClick={saveOverride} data-testid="override-save">
              Save Override
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
