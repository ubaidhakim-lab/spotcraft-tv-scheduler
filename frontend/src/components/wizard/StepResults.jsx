import { useState, useMemo } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import ChartFrame from "@/components/ChartFrame";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, CartesianGrid,
} from "recharts";

const CHART_COLORS = ["#002FA7", "#00B4D8", "#90E0EF", "#CAF0F8", "#03045E"];

function StatCard({ label, value, sublabel }) {
  return (
    <div className="bg-white border border-border p-5">
      <div className="overline">{label}</div>
      <div className="font-display text-3xl font-extrabold tracking-tight mt-1 tabular">
        {value}
      </div>
      {sublabel && (
        <div className="text-xs text-muted-foreground mt-1">{sublabel}</div>
      )}
    </div>
  );
}

export default function StepResults({ result, downloadHref }) {
  const [tab, setTab] = useState("edit");
  const [q, setQ] = useState("");

  const summary = result.summary;
  const editRows = result.edit_rows;
  const scheduleRows = result.schedule_rows;

  const filteredEdit = useMemo(
    () =>
      editRows.filter((r) =>
        [r.channel, r.program, r.market, r.genre]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(q.toLowerCase())
      ),
    [editRows, q]
  );
  const filteredSched = useMemo(
    () =>
      scheduleRows.filter((r) =>
        [r.channel, r.program, r.market, r.genre, r.day]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(q.toLowerCase())
      ),
    [scheduleRows, q]
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="overline">Step 4 · Review & Export</div>
          <h2 className="font-display text-3xl font-extrabold tracking-tight mt-1">
            Your ACD plan is ready
          </h2>
        </div>
        <a href={downloadHref} target="_blank" rel="noreferrer" data-testid="download-link">
          <Button data-testid="download-button">
            <Download className="h-4 w-4 mr-2" />
            Download Excel
          </Button>
        </a>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Edit FCT"
          value={`${summary.total_edit_fct.toLocaleString()}s`}
          sublabel="dispersed across edits"
        />
        <StatCard
          label="Total Spots"
          value={summary.total_edit_spots.toLocaleString()}
          sublabel="allocated in schedule"
        />
        <StatCard
          label="Total GRP"
          value={summary.total_grp.toLocaleString(undefined, { maximumFractionDigits: 2 })}
        />
        <StatCard
          label="Total Outlay"
          value={summary.total_outlay.toLocaleString(undefined, { maximumFractionDigits: 0 })}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white border border-border p-6">
          <div className="overline mb-3">Weekly Spot Distribution</div>
          <ChartFrame height={256} data-testid="weekly-chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={summary.by_week} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E4E4E7" />
                <XAxis dataKey="week" tickFormatter={(v) => `W${v}`} stroke="#52525B" />
                <YAxis stroke="#52525B" />
                <Tooltip />
                <Bar dataKey="spots" fill="#002FA7" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartFrame>
        </div>

        <div className="bg-white border border-border p-6">
          <div className="overline mb-3">Edit-wise Split</div>
          <ChartFrame height={256} data-testid="edit-pie">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={summary.by_edit}
                  dataKey="spots"
                  nameKey="duration"
                  outerRadius={80}
                  label={(e) => `${e.duration}s`}
                >
                  {summary.by_edit.map((_, i) => (
                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </ChartFrame>
        </div>
      </div>

      <div className="bg-white border border-border">
        <Tabs value={tab} onValueChange={setTab}>
          <div className="border-b border-border px-4 py-3 flex items-center justify-between gap-4">
            <TabsList data-testid="tabs-list">
              <TabsTrigger value="edit" data-testid="tab-edit">
                Edit-wise Plan ({editRows.length})
              </TabsTrigger>
              <TabsTrigger value="schedule" data-testid="tab-schedule">
                Day-wise Schedule ({scheduleRows.length})
              </TabsTrigger>
              <TabsTrigger value="channel" data-testid="tab-channel">
                By Channel
              </TabsTrigger>
            </TabsList>
            <input
              className="border border-border px-3 py-1.5 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="Filter channel/program/market..."
              value={q}
              onChange={(e) => setQ(e.target.value)}
              data-testid="filter-input"
            />
          </div>

          <TabsContent value="edit" className="m-0">
            <div className="overflow-auto max-h-[600px]">
              <table className="data-table w-full" data-testid="edit-table">
                <thead>
                  <tr>
                    <th>Market</th>
                    <th>Genre</th>
                    <th>Channel</th>
                    <th>Program</th>
                    <th>Days</th>
                    <th className="num">Edit</th>
                    <th className="num">Split %</th>
                    <th className="num">Edit FCT</th>
                    <th className="num">Spots</th>
                    <th className="num">GRP</th>
                    <th className="num">Outlay</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEdit.slice(0, 500).map((r, i) => (
                    <tr key={i}>
                      <td>{r.market}</td>
                      <td>{r.genre}</td>
                      <td className="font-semibold">{r.channel}</td>
                      <td>{r.program}</td>
                      <td>{r.days}</td>
                      <td className="num">{r.edit_duration}s</td>
                      <td className="num">{r.edit_pct}%</td>
                      <td className="num">{(r.final_fct || 0).toLocaleString()}</td>
                      <td className="num font-semibold">{r.final_spots}</td>
                      <td className="num">{(r.grp || 0).toLocaleString()}</td>
                      <td className="num">{(r.net_outlay || 0).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TabsContent>

          <TabsContent value="schedule" className="m-0">
            <div className="overflow-auto max-h-[600px]">
              <table className="data-table w-full" data-testid="schedule-table">
                <thead>
                  <tr>
                    <th>Week</th>
                    <th>Date</th>
                    <th>Day</th>
                    <th>Market</th>
                    <th>Channel</th>
                    <th>Program</th>
                    <th className="num">Edit</th>
                    <th className="num">Spot Time</th>
                    <th>Daypart</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSched.slice(0, 1000).map((r, i) => (
                    <tr key={i}>
                      <td>W{r.week}</td>
                      <td>{r.date}</td>
                      <td>{r.day}</td>
                      <td>{r.market}</td>
                      <td className="font-semibold">{r.channel}</td>
                      <td>{r.program}</td>
                      <td className="num">{r.edit_duration}s</td>
                      <td className="num">{r.spot_time}</td>
                      <td>{r.daypart}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filteredSched.length > 1000 && (
                <div className="p-3 text-xs text-muted-foreground border-t border-border">
                  Showing 1,000 of {filteredSched.length}. Full data in Excel export.
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="channel" className="m-0">
            <div className="overflow-auto max-h-[600px]">
              <table className="data-table w-full" data-testid="channel-table">
                <thead>
                  <tr>
                    <th>Channel</th>
                    <th className="num">Spots</th>
                    <th className="num">FCT</th>
                    <th className="num">Outlay</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.by_channel.map((c, i) => (
                    <tr key={i}>
                      <td className="font-semibold">{c.channel}</td>
                      <td className="num">{c.spots.toLocaleString()}</td>
                      <td className="num">{c.fct.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                      <td className="num">{c.outlay.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
