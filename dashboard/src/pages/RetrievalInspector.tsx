import { useState } from 'react';
import { api } from '../lib/api';
import type { InspectResult, ChunkItem } from '../lib/api';
import { Search, ChevronDown, ChevronRight } from 'lucide-react';

function Badge({ label, color = 'blue' }: { label: string; color?: string }) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-700',
    purple: 'bg-purple-50 text-purple-700',
    green: 'bg-green-50 text-green-700',
    gray: 'bg-gray-100 text-gray-600',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colors[color] ?? colors.blue}`}>
      {label}
    </span>
  );
}

function ChunkCard({ chunk, rank }: { chunk: ChunkItem; rank: number; label?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 bg-white hover:bg-gray-50 text-left"
      >
        <span className="text-xs font-mono text-gray-400 w-6 text-right">#{rank}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-gray-900 truncate">{chunk.source_name}</span>
            {chunk.section && <Badge label={chunk.section} color="blue" />}
            {chunk.procedure_tags.slice(0, 2).map(t => <Badge key={t} label={t} color="purple" />)}
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className={`text-sm font-semibold tabular-nums ${chunk.similarity >= 0.7 ? 'text-green-600' : chunk.similarity >= 0.55 ? 'text-yellow-600' : 'text-red-500'}`}>
            {chunk.similarity.toFixed(3)}
          </span>
          <span className="text-gray-400">{open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</span>
        </div>
      </button>
      {open && (
        <div className="px-4 py-3 bg-gray-50 border-t border-gray-200">
          <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{chunk.content}</p>
        </div>
      )}
    </div>
  );
}

export default function RetrievalInspector() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<InspectResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.inspect(query.trim()));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold text-gray-900 mb-1">Retrieval Inspector</h1>
      <p className="text-sm text-gray-500 mb-5">Trace the full pipeline: route → rewrite → retrieve → rerank → generate</p>

      {/* Query input */}
      <div className="flex gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && run()}
            placeholder="Enter a query to inspect…"
            className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          />
        </div>
        <button
          onClick={run}
          disabled={loading || !query.trim()}
          className="px-5 py-2.5 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
        >
          {loading ? 'Running…' : 'Inspect'}
        </button>
      </div>

      {error && <div className="bg-red-50 text-red-700 text-sm rounded-md p-3 mb-4">{error}</div>}

      {result && (
        <div className="space-y-5">
          {/* Route decision */}
          <section className="bg-white border border-gray-200 rounded-lg p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">1. Route Decision</h2>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-gray-500 text-xs uppercase tracking-wide">In Scope</span>
                <div className="mt-1">{result.route.in_scope
                  ? <Badge label="in scope" color="green" />
                  : <Badge label="blocked" color="gray" />}
                </div>
              </div>
              <div>
                <span className="text-gray-500 text-xs uppercase tracking-wide">Pipeline</span>
                <div className="mt-1"><Badge label={result.route.pipeline} color="blue" /></div>
              </div>
              <div>
                <span className="text-gray-500 text-xs uppercase tracking-wide">Intent</span>
                <div className="mt-1"><Badge label={result.route.intent} color="purple" /></div>
              </div>
              <div>
                <span className="text-gray-500 text-xs uppercase tracking-wide">Source Type</span>
                <div className="mt-1 text-gray-700">{result.route.source_type || '—'}</div>
              </div>
              <div>
                <span className="text-gray-500 text-xs uppercase tracking-wide">Procedure Tags</span>
                <div className="mt-1 flex gap-1 flex-wrap">
                  {result.route.procedure_tags.length
                    ? result.route.procedure_tags.map(t => <Badge key={t} label={t} color="purple" />)
                    : <span className="text-gray-400">none</span>}
                </div>
              </div>
              <div>
                <span className="text-gray-500 text-xs uppercase tracking-wide">Sections</span>
                <div className="mt-1 flex gap-1 flex-wrap">
                  {result.route.sections.length
                    ? result.route.sections.map(s => <Badge key={s} label={s} color="blue" />)
                    : <span className="text-gray-400">all sections</span>}
                </div>
              </div>
            </div>
          </section>

          {/* Query rewrite */}
          <section className="bg-white border border-gray-200 rounded-lg p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">2. Query Rewrite</h2>
            <div className="space-y-2">
              <div>
                <span className="text-xs text-gray-500 uppercase tracking-wide">Original</span>
                <p className="mt-1 text-sm text-gray-700 italic">"{result.query}"</p>
              </div>
              <div>
                <span className="text-xs text-gray-500 uppercase tracking-wide">Rewritten (retrieval query)</span>
                <p className="mt-1 text-sm text-gray-900 font-medium">"{result.rewritten_query}"</p>
              </div>
            </div>
          </section>

          {/* Retrieved chunks */}
          <section>
            <h2 className="text-sm font-semibold text-gray-700 mb-3">
              3. Retrieved Chunks (pre-rerank) — {result.retrieved_chunks.length} results
            </h2>
            <div className="space-y-2">
              {result.retrieved_chunks.length === 0
                ? <div className="bg-yellow-50 text-yellow-700 text-sm rounded-md p-3">No chunks retrieved — try relaxing the query or check that the knowledge base is seeded.</div>
                : result.retrieved_chunks.map((c, i) => (
                    <ChunkCard key={c.id} chunk={c} rank={i + 1} label="pre-rerank" />
                  ))}
            </div>
          </section>

          {/* Reranked chunks */}
          <section>
            <h2 className="text-sm font-semibold text-gray-700 mb-3">
              4. Reranked Chunks (sent to Claude) — top {result.reranked_chunks.length}
            </h2>
            <div className="space-y-2">
              {result.reranked_chunks.length === 0
                ? <div className="text-gray-400 text-sm">No chunks after reranking.</div>
                : result.reranked_chunks.map((c, i) => (
                    <ChunkCard key={c.id} chunk={c} rank={i + 1} label="post-rerank" />
                  ))}
            </div>
          </section>

          {/* Response */}
          <section className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-700">5. Generated Response</h2>
              <div className="flex gap-3 text-xs text-gray-500">
                <span>{result.input_tokens.toLocaleString()} in / {result.output_tokens.toLocaleString()} out tokens</span>
                <span>${result.cost_usd.toFixed(4)}</span>
                <span>{result.latency_ms.toLocaleString()}ms</span>
              </div>
            </div>
            <div className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed bg-gray-50 rounded-md p-3">
              {result.response}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
