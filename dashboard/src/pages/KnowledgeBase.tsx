import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { Chunk, ChunkStats } from '../lib/api';
import { Search, Trash2, ChevronDown, ChevronRight } from 'lucide-react';

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-2xl font-semibold text-gray-900 mt-1">{value.toLocaleString()}</div>
    </div>
  );
}

function ChunkRow({ chunk, onDelete }: { chunk: Chunk; onDelete: () => void }) {
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    if (!confirm(`Delete chunk from "${chunk.source_name}"?`)) return;
    setDeleting(true);
    try {
      await api.deleteChunk(chunk.id);
      onDelete();
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 bg-white">
        <button onClick={() => setOpen(!open)} className="text-gray-400 hover:text-gray-600">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-gray-900 truncate">{chunk.source_name}</span>
            {chunk.section && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-blue-50 text-blue-700">{chunk.section}</span>
            )}
            {chunk.source_type !== 'procedure' && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600">{chunk.source_type}</span>
            )}
            {chunk.procedure_tags?.slice(0, 2).map(t => (
              <span key={t} className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-purple-50 text-purple-700">{t}</span>
            ))}
          </div>
          <div className="text-xs text-gray-400 mt-0.5 truncate">{chunk.content.slice(0, 100)}…</div>
        </div>
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="shrink-0 p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors disabled:opacity-40"
          title="Delete chunk"
        >
          <Trash2 size={14} />
        </button>
      </div>
      {open && (
        <div className="px-4 py-3 bg-gray-50 border-t border-gray-200">
          <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{chunk.content}</p>
          <div className="mt-2 text-xs text-gray-400">
            ID: {chunk.id} · Created: {new Date(chunk.created_at).toLocaleString()}
          </div>
        </div>
      )}
    </div>
  );
}

const SECTIONS = ['', 'description', 'editorial_summary', 'who_its_for', 'what_is_normal', 'what_to_watch_for', 'recovery_overview', 'consult_questions'];
const SOURCE_TYPES = ['', 'procedure', 'medical_paper', 'guide', 'faq'];

export default function KnowledgeBase() {
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [stats, setStats] = useState<ChunkStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [section, setSection] = useState('');
  const [sourceType, setSourceType] = useState('');
  const [procedure, setProcedure] = useState('');
  const [offset, setOffset] = useState(0);
  const limit = 50;

  function loadStats() {
    api.chunkStats().then(setStats).catch(() => {});
  }

  function loadChunks() {
    setLoading(true);
    setError(null);
    api.chunks({ limit, offset, search: search || undefined, section: section || undefined, source_type: sourceType || undefined, procedure: procedure || undefined })
      .then(r => setChunks(r.data))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { loadStats(); }, []);
  useEffect(() => { loadChunks(); }, [offset, search, section, sourceType, procedure]);

  function handleDelete() {
    loadChunks();
    loadStats();
  }

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold text-gray-900 mb-1">Knowledge Base</h1>
      <p className="text-sm text-gray-500 mb-5">Browse, search, and delete entries in knowledge_chunks</p>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-4 gap-3 mb-5">
          <StatCard label="Total Chunks" value={stats.total} />
          <StatCard label="Procedures" value={Object.keys(stats.by_procedure).length} />
          <StatCard label="Sections" value={Object.keys(stats.by_section).length} />
          <StatCard label="Source Types" value={Object.keys(stats.by_source).length} />
        </div>
      )}

      {/* Top procedures */}
      {stats && Object.keys(stats.by_procedure).length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-5">
          <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Chunks by Procedure (top 10)</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(stats.by_procedure).slice(0, 10).map(([proc, count]) => (
              <button
                key={proc}
                onClick={() => { setProcedure(p => p === proc ? '' : proc); setOffset(0); }}
                className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${procedure === proc ? 'bg-purple-600 text-white border-purple-600' : 'bg-white text-gray-700 border-gray-300 hover:border-purple-400'}`}
              >
                {proc} ({count})
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={14} />
          <input
            type="text"
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { setSearch(searchInput); setOffset(0); } }}
            placeholder="Search content…"
            className="w-full pl-8 pr-4 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          />
        </div>
        <select value={section} onChange={e => { setSection(e.target.value); setOffset(0); }}
          className="text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-700">
          {SECTIONS.map(s => <option key={s} value={s}>{s || 'All sections'}</option>)}
        </select>
        <select value={sourceType} onChange={e => { setSourceType(e.target.value); setOffset(0); }}
          className="text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-700">
          {SOURCE_TYPES.map(s => <option key={s} value={s}>{s || 'All source types'}</option>)}
        </select>
        {(search || section || sourceType || procedure) && (
          <button onClick={() => { setSearch(''); setSearchInput(''); setSection(''); setSourceType(''); setProcedure(''); setOffset(0); }}
            className="text-xs px-3 py-1.5 rounded-md bg-gray-100 text-gray-600 hover:bg-gray-200">
            Clear filters
          </button>
        )}
      </div>

      {error && <div className="bg-red-50 text-red-700 text-sm rounded-md p-3 mb-4">{error}</div>}

      {/* Chunks list */}
      <div className="space-y-2">
        {loading && <div className="text-sm text-gray-400 py-8 text-center">Loading…</div>}
        {!loading && chunks.length === 0 && (
          <div className="text-sm text-gray-400 py-8 text-center">
            No chunks found. {!stats?.total && 'Run the ingestion pipeline to seed the knowledge base.'}
          </div>
        )}
        {!loading && chunks.map(c => (
          <ChunkRow key={c.id} chunk={c} onDelete={handleDelete} />
        ))}
      </div>

      {/* Pagination */}
      {chunks.length > 0 && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-xs text-gray-500">Showing {offset + 1}–{offset + chunks.length}</span>
          <div className="flex gap-2">
            <button onClick={() => setOffset(Math.max(0, offset - limit))} disabled={offset === 0}
              className="text-xs px-3 py-1.5 rounded border border-gray-300 bg-white disabled:opacity-40 hover:bg-gray-100">
              Previous
            </button>
            <button onClick={() => setOffset(offset + limit)} disabled={chunks.length < limit}
              className="text-xs px-3 py-1.5 rounded border border-gray-300 bg-white disabled:opacity-40 hover:bg-gray-100">
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
