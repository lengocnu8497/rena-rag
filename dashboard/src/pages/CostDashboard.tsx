import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { CostRow } from '../lib/api';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';

function MetricCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-xl font-semibold text-gray-900 mt-1">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );
}

const COLORS = {
  sonnet: '#7c3aed',
  haiku: '#2563eb',
  embed: '#059669',
  total: '#111827',
};

export default function CostDashboard() {
  const [rows, setRows] = useState<CostRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.costSummary(days)
      .then(r => setRows(r.data))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [days]);

  const totalRequests = rows.reduce((s, r) => s + r.requests, 0);
  const totalCost = rows.reduce((s, r) => s + r.total_cost, 0);
  const totalSonnet = rows.reduce((s, r) => s + r.sonnet_cost, 0);
  const totalHaiku = rows.reduce((s, r) => s + r.haiku_cost, 0);
  const avgLatency = rows.length ? Math.round(rows.reduce((s, r) => s + r.mean_latency_ms, 0) / rows.length) : 0;

  const chartData = rows.map(r => ({
    ...r,
    date: r.date.slice(5),  // show MM-DD not YYYY-MM-DD
    sonnet_cost_mc: +(r.sonnet_cost * 1000).toFixed(3),
    haiku_cost_mc: +(r.haiku_cost * 1000).toFixed(3),
    embed_cost_mc: +(r.embed_cost * 1000).toFixed(3),
    total_cost_mc: +(r.total_cost * 1000).toFixed(3),
  }));

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-semibold text-gray-900">Cost Dashboard</h1>
        <select value={days} onChange={e => setDays(+e.target.value)}
          className="text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-700">
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>
      <p className="text-sm text-gray-500 mb-5">Daily API spend by model from rag_eval_logs</p>

      {error && <div className="bg-red-50 text-red-700 text-sm rounded-md p-3 mb-4">{error}</div>}

      {/* Summary cards */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        <MetricCard label="Total Requests" value={totalRequests.toLocaleString()} />
        <MetricCard label="Total Cost" value={`$${totalCost.toFixed(4)}`} sub={`${days} days`} />
        <MetricCard label="Sonnet Cost" value={`$${totalSonnet.toFixed(4)}`} sub="generation model" />
        <MetricCard label="Haiku Cost" value={`$${totalHaiku.toFixed(4)}`} sub="routing + reranking" />
        <MetricCard label="Avg Latency" value={`${avgLatency.toLocaleString()}ms`} sub="mean end-to-end" />
      </div>

      {loading && <div className="text-sm text-gray-400 text-center py-20">Loading…</div>}

      {!loading && rows.length === 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg py-20 text-center text-sm text-gray-400">
          No cost data yet — eval logs populate this chart.
        </div>
      )}

      {!loading && rows.length > 0 && (
        <div className="space-y-5">
          {/* Stacked area: cost by model */}
          <div className="bg-white border border-gray-200 rounded-lg p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">Daily Cost by Model (millicents)</h2>
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={chartData} margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `${v}¢`} />
                <Tooltip formatter={(v) => [`${v}¢`, '']} />
                <Legend />
                <Area type="monotone" dataKey="sonnet_cost_mc" name="Sonnet" stackId="1" stroke={COLORS.sonnet} fill={COLORS.sonnet} fillOpacity={0.7} />
                <Area type="monotone" dataKey="haiku_cost_mc" name="Haiku" stackId="1" stroke={COLORS.haiku} fill={COLORS.haiku} fillOpacity={0.7} />
                <Area type="monotone" dataKey="embed_cost_mc" name="Embeddings" stackId="1" stroke={COLORS.embed} fill={COLORS.embed} fillOpacity={0.7} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Requests + latency bar chart */}
          <div className="grid grid-cols-2 gap-5">
            <div className="bg-white border border-gray-200 rounded-lg p-5">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">Daily Requests</h2>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={chartData} margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="requests" name="Requests" fill={COLORS.sonnet} radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-white border border-gray-200 rounded-lg p-5">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">Mean Latency (ms)</h2>
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={chartData} margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v) => [`${v}ms`, 'Latency']} />
                  <Area type="monotone" dataKey="mean_latency_ms" name="Latency" stroke="#f59e0b" fill="#fef3c7" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Data table */}
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-700">Raw Data</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    {['Date', 'Requests', 'Total', 'Sonnet', 'Haiku', 'Embed', 'Avg Latency'].map(h => (
                      <th key={h} className="text-left px-3 py-2 font-medium text-gray-500 uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {[...chartData].reverse().map(r => (
                    <tr key={r.date} className="hover:bg-gray-50">
                      <td className="px-3 py-2 text-gray-700 font-mono">{r.date}</td>
                      <td className="px-3 py-2 text-gray-700">{r.requests}</td>
                      <td className="px-3 py-2 text-gray-900 font-medium">${r.total_cost.toFixed(4)}</td>
                      <td className="px-3 py-2 text-purple-700">${r.sonnet_cost.toFixed(4)}</td>
                      <td className="px-3 py-2 text-blue-700">${r.haiku_cost.toFixed(4)}</td>
                      <td className="px-3 py-2 text-green-700">${r.embed_cost.toFixed(4)}</td>
                      <td className="px-3 py-2 text-gray-700">{r.mean_latency_ms.toLocaleString()}ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
