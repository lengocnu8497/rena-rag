import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { EvalLog } from '../lib/api';

function score(v: number | null, good = 0.7) {
  if (v === null) return <span className="text-gray-400">—</span>;
  const color = v >= good ? 'text-green-600' : v >= good * 0.7 ? 'text-yellow-600' : 'text-red-600';
  return <span className={color}>{v.toFixed(2)}</span>;
}

function ms(v: number | null) {
  if (v === null) return <span className="text-gray-400">—</span>;
  const color = v < 5000 ? 'text-gray-700' : v < 10000 ? 'text-yellow-600' : 'text-red-600';
  return <span className={color}>{v.toLocaleString()}ms</span>;
}

function usd(v: number | null) {
  if (v === null) return <span className="text-gray-400">—</span>;
  return <span className="text-gray-700">${(v * 1000).toFixed(3)}¢</span>;
}

const INTENTS = ['', 'recovery_question', 'consult_prep', 'procedure_info', 'general_advice', 'out_of_scope'];
const PIPELINES = ['', 'deterministic', 'agent', 'blocked'];

export default function EvalResults() {
  const [logs, setLogs] = useState<EvalLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [intent, setIntent] = useState('');
  const [pipeline, setPipeline] = useState('');
  const [scopeBlocked, setScopeBlocked] = useState<string>('');
  const limit = 50;

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.evalLogs({
      limit,
      offset,
      intent: intent || undefined,
      pipeline_mode: pipeline || undefined,
      scope_blocked: scopeBlocked === 'true' ? true : scopeBlocked === 'false' ? false : undefined,
    })
      .then((r) => setLogs(r.data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [offset, intent, pipeline, scopeBlocked]);

  const avgFaith = logs.filter(l => l.faithfulness_score !== null).reduce((s, l) => s + (l.faithfulness_score ?? 0), 0) / (logs.filter(l => l.faithfulness_score !== null).length || 1);
  const avgSim = logs.filter(l => l.mean_retrieval_score !== null).reduce((s, l) => s + (l.mean_retrieval_score ?? 0), 0) / (logs.filter(l => l.mean_retrieval_score !== null).length || 1);

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold text-gray-900 mb-1">Eval Results</h1>
      <p className="text-sm text-gray-500 mb-5">Per-request quality telemetry from rag_eval_logs</p>

      {/* Summary cards */}
      {logs.length > 0 && (
        <div className="grid grid-cols-4 gap-3 mb-5">
          {[
            { label: 'Requests', value: logs.length },
            { label: 'Avg Faithfulness', value: avgFaith.toFixed(2), good: avgFaith >= 0.7 },
            { label: 'Avg Retrieval Sim', value: avgSim.toFixed(3), good: avgSim >= 0.55 },
            { label: 'Blocked', value: logs.filter(l => l.scope_blocked).length },
          ].map(({ label, value, good }) => (
            <div key={label} className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="text-xs text-gray-500">{label}</div>
              <div className={`text-2xl font-semibold mt-1 ${good === false ? 'text-red-600' : good === true ? 'text-green-600' : 'text-gray-900'}`}>
                {value}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <select value={intent} onChange={e => { setIntent(e.target.value); setOffset(0); }}
          className="text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-700">
          {INTENTS.map(i => <option key={i} value={i}>{i || 'All intents'}</option>)}
        </select>
        <select value={pipeline} onChange={e => { setPipeline(e.target.value); setOffset(0); }}
          className="text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-700">
          {PIPELINES.map(p => <option key={p} value={p}>{p || 'All pipelines'}</option>)}
        </select>
        <select value={scopeBlocked} onChange={e => { setScopeBlocked(e.target.value); setOffset(0); }}
          className="text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-700">
          <option value="">All</option>
          <option value="false">In-scope</option>
          <option value="true">Blocked</option>
        </select>
      </div>

      {error && <div className="bg-red-50 text-red-700 text-sm rounded-md p-3 mb-4">{error}</div>}

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['Time', 'Query', 'Intent', 'Pipeline', 'Faith', 'Sim', 'Latency', 'Cost', 'Blocked'].map(h => (
                  <th key={h} className="text-left px-3 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading && (
                <tr><td colSpan={9} className="px-3 py-8 text-center text-gray-400">Loading…</td></tr>
              )}
              {!loading && logs.length === 0 && (
                <tr><td colSpan={9} className="px-3 py-8 text-center text-gray-400">No eval logs yet — make some requests to /chat first.</td></tr>
              )}
              {!loading && logs.map((log) => (
                <tr key={log.id} className="hover:bg-gray-50">
                  <td className="px-3 py-2.5 text-gray-500 whitespace-nowrap text-xs">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2.5 text-gray-900 max-w-xs">
                    <div className="truncate" title={log.query}>{log.query}</div>
                  </td>
                  <td className="px-3 py-2.5 text-gray-600 whitespace-nowrap">
                    {log.intent ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-blue-50 text-blue-700">{log.intent}</span>
                    ) : '—'}
                  </td>
                  <td className="px-3 py-2.5 text-gray-600 whitespace-nowrap text-xs">{log.pipeline_mode || '—'}</td>
                  <td className="px-3 py-2.5 whitespace-nowrap">{score(log.faithfulness_score, 0.7)}</td>
                  <td className="px-3 py-2.5 whitespace-nowrap">{score(log.mean_retrieval_score, 0.55)}</td>
                  <td className="px-3 py-2.5 whitespace-nowrap">{ms(log.latency_ms)}</td>
                  <td className="px-3 py-2.5 whitespace-nowrap">{usd(log.cost_usd)}</td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    {log.scope_blocked && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-red-50 text-red-600">blocked</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-3 py-2.5 border-t border-gray-100 bg-gray-50">
          <span className="text-xs text-gray-500">Showing {offset + 1}–{offset + logs.length}</span>
          <div className="flex gap-2">
            <button onClick={() => setOffset(Math.max(0, offset - limit))} disabled={offset === 0}
              className="text-xs px-3 py-1.5 rounded border border-gray-300 bg-white disabled:opacity-40 hover:bg-gray-100">
              Previous
            </button>
            <button onClick={() => setOffset(offset + limit)} disabled={logs.length < limit}
              className="text-xs px-3 py-1.5 rounded border border-gray-300 bg-white disabled:opacity-40 hover:bg-gray-100">
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
