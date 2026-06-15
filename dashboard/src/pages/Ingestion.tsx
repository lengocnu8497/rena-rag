import { useRef, useState } from 'react';
import { Upload, CheckCircle, AlertCircle, Terminal, FileText, Sparkles, X } from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ProcedureSeedException {
  status: 'idle' | 'running' | 'done' | 'error';
  message: string;
}

interface SidecarSuggestion {
  source_name: string;
  source_type: string;
  procedure_tags: string[];
  paper_year: number | null;
  preview_text: string;
}

interface PdfState {
  phase: 'idle' | 'suggesting' | 'editing' | 'ingesting' | 'done' | 'error';
  file: File | null;
  suggestion: SidecarSuggestion | null;
  // editable form fields
  source_name: string;
  source_type: string;
  procedure_tags: string[];   // stored as array, shown as chips
  tagInput: string;
  paper_year: string;
  // result
  chunks_added: number | null;
  error: string | null;
}

const INITIAL_PDF: PdfState = {
  phase: 'idle', file: null, suggestion: null,
  source_name: '', source_type: 'medical_paper', procedure_tags: [],
  tagInput: '', paper_year: '',
  chunks_added: null, error: null,
};

const VALID_PROCEDURES = [
  'rhinoplasty', 'facelift', 'blepharoplasty', 'brow lift', 'neck lift',
  'chin augmentation', 'otoplasty', 'breast augmentation', 'breast lift',
  'breast reduction', 'brazilian butt lift', 'mommy makeover', 'microneedling',
  'chemical peel', 'laser resurfacing', 'ipl photofacial', 'hydrafacial',
  'ultherapy / hifu', 'rf microneedling', 'laser hair removal', 'botox / dysport',
  'lip filler', 'cheek filler', 'jawline filler', 'under eye filler',
  'dermal filler', 'kybella', 'sculptra', 'prp / prf therapy', 'coolsculpting',
  'emsculpt / emsculpt neo', 'rf skin tightening', 'pdo thread lift',
  'microfocused ultrasound', 'liposuction', 'tummy tuck', 'fat transfer',
  'body contouring surgery',
];

const SOURCE_TYPES = ['medical_paper', 'guide', 'faq'];

// ─── Component ────────────────────────────────────────────────────────────────

export default function Ingestion() {
  const [seed, setSeed] = useState<ProcedureSeedException>({ status: 'idle', message: '' });
  const [pdf, setPdf] = useState<PdfState>(INITIAL_PDF);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // ── Procedure seed ──────────────────────────────────────────────────────────

  async function triggerSeed() {
    setSeed({ status: 'running', message: '' });
    try {
      const res = await fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: 'procedures' }),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setSeed({ status: 'done', message: 'Ingestion started — check Knowledge Base in ~30s.' });
    } catch (e) {
      setSeed({ status: 'error', message: (e as Error).message });
    }
  }

  // ── PDF flow ────────────────────────────────────────────────────────────────

  async function handleFile(file: File) {
    if (!file.name.toLowerCase().endsWith('.pdf')) return;
    setPdf({ ...INITIAL_PDF, file, phase: 'suggesting' });

    const form = new FormData();
    form.append('file', file);

    try {
      const res = await fetch('/api/ingest/pdf/suggest', { method: 'POST', body: form });
      if (!res.ok) throw new Error(await res.text());
      const s: SidecarSuggestion = await res.json();
      setPdf(p => ({
        ...p,
        phase: 'editing',
        suggestion: s,
        source_name: s.source_name,
        source_type: s.source_type,
        procedure_tags: s.procedure_tags,
        paper_year: s.paper_year ? String(s.paper_year) : '',
      }));
    } catch (e) {
      setPdf(p => ({ ...p, phase: 'error', error: (e as Error).message }));
    }
  }

  async function ingestPdf() {
    if (!pdf.file) return;
    setPdf(p => ({ ...p, phase: 'ingesting', error: null }));

    const form = new FormData();
    form.append('file', pdf.file);
    form.append('source_name', pdf.source_name);
    form.append('source_type', pdf.source_type);
    form.append('procedure_tags', JSON.stringify(pdf.procedure_tags));
    form.append('paper_year', pdf.paper_year);

    try {
      const res = await fetch('/api/ingest/pdf', { method: 'POST', body: form });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setPdf(p => ({ ...p, phase: 'done', chunks_added: data.chunks_added }));
    } catch (e) {
      setPdf(p => ({ ...p, phase: 'error', error: (e as Error).message }));
    }
  }

  function addTag(tag: string) {
    const t = tag.trim().toLowerCase();
    if (t && !pdf.procedure_tags.includes(t)) {
      setPdf(p => ({ ...p, procedure_tags: [...p.procedure_tags, t], tagInput: '' }));
    } else {
      setPdf(p => ({ ...p, tagInput: '' }));
    }
  }

  function removeTag(tag: string) {
    setPdf(p => ({ ...p, procedure_tags: p.procedure_tags.filter(t => t !== tag) }));
  }

  const canIngest = pdf.source_name.trim().length > 0 && pdf.procedure_tags.length > 0;

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Ingestion</h1>
        <p className="text-sm text-gray-500 mt-0.5">Seed procedures or upload medical PDFs into the knowledge base</p>
      </div>

      {/* ── Row 1: Procedure seed + CLI ─────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-5">

        {/* Seed from DB */}
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <div className="flex items-center gap-2.5 mb-3">
            <div className="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center">
              <Upload className="text-purple-600" size={16} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-gray-900">Re-seed from Procedures DB</h2>
              <p className="text-xs text-gray-500">38 procedures × 7 sections → ~266 chunks</p>
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-4">
            Reads all procedure rows from Supabase, chunks by section, embeds, and upserts. Safe to re-run — idempotent.
          </p>
          {seed.status === 'running' ? (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <div className="w-4 h-4 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
              Starting…
            </div>
          ) : (
            <button onClick={triggerSeed}
              className="px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 transition-colors">
              Trigger Ingestion
            </button>
          )}
          {seed.status === 'done' && (
            <div className="mt-3 flex items-center gap-2 bg-green-50 text-green-700 text-sm rounded-md p-3">
              <CheckCircle size={14} />{seed.message}
            </div>
          )}
          {seed.status === 'error' && (
            <div className="mt-3 flex items-start gap-2 bg-red-50 text-red-700 text-sm rounded-md p-3">
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              <span className="font-mono text-xs">{seed.message}</span>
            </div>
          )}
        </div>

        {/* CLI reference */}
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <div className="flex items-center gap-2.5 mb-3">
            <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center">
              <Terminal className="text-gray-600" size={16} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-gray-900">CLI Commands</h2>
              <p className="text-xs text-gray-500">Run from /Users/nule/Documents/rena-rag/</p>
            </div>
          </div>
          <div className="space-y-2.5">
            {[
              { label: 'Seed from procedures', cmd: 'uv run python -m app.ingestion.ingest' },
              { label: 'Ingest PDF directory', cmd: 'uv run python -m app.ingestion.ingest --pdf-dir /path/to/pdfs/' },
              { label: 'Run full eval harness', cmd: 'uv run python -m evals.harness' },
            ].map(({ label, cmd }) => (
              <div key={cmd}>
                <div className="text-xs text-gray-500 mb-1">{label}</div>
                <div className="bg-gray-900 text-green-400 rounded-md px-3 py-1.5 text-xs font-mono">$ {cmd}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Row 2: PDF Upload ────────────────────────────────────────────────── */}
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <div className="flex items-center gap-2.5 mb-4">
          <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
            <FileText className="text-blue-600" size={16} />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Upload Medical PDF</h2>
            <p className="text-xs text-gray-500">
              Haiku reads the abstract and suggests all metadata fields — review and ingest in one click
            </p>
          </div>
        </div>

        {/* Drop zone — shown when idle or after reset */}
        {(pdf.phase === 'idle' || pdf.phase === 'done') && (
          <>
            {pdf.phase === 'done' && (
              <div className="mb-4 flex items-center gap-2 bg-green-50 text-green-700 text-sm rounded-md p-3">
                <CheckCircle size={14} />
                <span>
                  <strong>{pdf.source_name}</strong> ingested — {pdf.chunks_added} chunks added to the knowledge base.
                </span>
                <button onClick={() => setPdf(INITIAL_PDF)} className="ml-auto text-xs underline">Upload another</button>
              </div>
            )}
            <div
              onDragOver={e => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
              onClick={() => fileRef.current?.click()}
              className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors ${dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'}`}
            >
              <Upload className="mx-auto mb-2 text-gray-400" size={24} />
              <p className="text-sm text-gray-600 font-medium">Drop a PDF here or <span className="text-blue-600 underline">browse</span></p>
              <p className="text-xs text-gray-400 mt-1">Max 50 MB · research papers, guides, clinical reviews</p>
              <input ref={fileRef} type="file" accept=".pdf" className="hidden"
                onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
            </div>
          </>
        )}

        {/* Suggesting spinner */}
        {pdf.phase === 'suggesting' && (
          <div className="rounded-lg border border-blue-200 bg-blue-50 p-6 text-center">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm font-medium text-blue-800">Reading PDF…</p>
            <p className="text-xs text-blue-600 mt-1">
              Haiku is extracting the abstract and suggesting metadata
            </p>
          </div>
        )}

        {/* Edit form */}
        {(pdf.phase === 'editing' || pdf.phase === 'ingesting') && (
          <div className="space-y-4">
            {/* Preview banner */}
            {pdf.suggestion?.preview_text && (
              <div className="rounded-md bg-gray-50 border border-gray-200 p-3">
                <div className="flex items-center gap-1.5 text-xs font-medium text-gray-500 mb-1.5">
                  <Sparkles size={12} className="text-purple-500" />
                  AI-suggested from abstract — review before ingesting
                </div>
                <p className="text-xs text-gray-600 line-clamp-3 leading-relaxed">
                  {pdf.suggestion.preview_text}
                </p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              {/* Source name */}
              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Source Name <span className="text-red-500">*</span>
                </label>
                <input type="text" value={pdf.source_name}
                  onChange={e => setPdf(p => ({ ...p, source_name: e.target.value }))}
                  placeholder="Smith et al. 2023 — Botox Longevity Study"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>

              {/* Source type */}
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Source Type</label>
                <select value={pdf.source_type}
                  onChange={e => setPdf(p => ({ ...p, source_type: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                  {SOURCE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>

              {/* Paper year */}
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Publication Year</label>
                <input type="number" value={pdf.paper_year} min={1990} max={2099}
                  onChange={e => setPdf(p => ({ ...p, paper_year: e.target.value }))}
                  placeholder="2024"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>

              {/* Procedure tags */}
              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Procedure Tags <span className="text-red-500">*</span>
                  <span className="font-normal text-gray-400 ml-1">(must match exact procedure names)</span>
                </label>
                {/* Chips */}
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {pdf.procedure_tags.map(tag => (
                    <span key={tag} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-purple-100 text-purple-800">
                      {tag}
                      <button onClick={() => removeTag(tag)} className="hover:text-red-600"><X size={10} /></button>
                    </span>
                  ))}
                </div>
                {/* Autocomplete input */}
                <div className="relative">
                  <input
                    type="text"
                    value={pdf.tagInput}
                    onChange={e => setPdf(p => ({ ...p, tagInput: e.target.value }))}
                    onKeyDown={e => {
                      if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag(pdf.tagInput); }
                    }}
                    placeholder="Type a procedure name and press Enter…"
                    list="procedure-list"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <datalist id="procedure-list">
                    {VALID_PROCEDURES.filter(p => !pdf.procedure_tags.includes(p)).map(p => (
                      <option key={p} value={p} />
                    ))}
                  </datalist>
                </div>
                {/* Quick-add chips */}
                <div className="mt-2 flex flex-wrap gap-1">
                  {VALID_PROCEDURES.filter(p => !pdf.procedure_tags.includes(p)).slice(0, 12).map(p => (
                    <button key={p} onClick={() => addTag(p)}
                      className="text-xs px-2 py-0.5 rounded-full border border-gray-300 text-gray-600 hover:border-purple-400 hover:text-purple-700 hover:bg-purple-50 transition-colors">
                      + {p}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Action row */}
            <div className="flex items-center gap-3 pt-1">
              <button
                onClick={ingestPdf}
                disabled={!canIngest || pdf.phase === 'ingesting'}
                className="px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                {pdf.phase === 'ingesting' && (
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                )}
                {pdf.phase === 'ingesting' ? 'Ingesting…' : 'Ingest PDF'}
              </button>
              <button onClick={() => setPdf(INITIAL_PDF)}
                className="text-sm text-gray-500 hover:text-gray-700 underline">
                Cancel
              </button>
              {!canIngest && (
                <span className="text-xs text-gray-400">Source name and at least one procedure tag are required.</span>
              )}
            </div>
          </div>
        )}

        {/* Error state */}
        {pdf.phase === 'error' && (
          <div className="mt-3 flex items-start gap-2 bg-red-50 text-red-700 text-sm rounded-md p-3">
            <AlertCircle size={14} className="mt-0.5 shrink-0" />
            <div>
              <div className="font-medium">Failed</div>
              <div className="text-xs mt-1 font-mono">{pdf.error}</div>
              <button onClick={() => setPdf(INITIAL_PDF)} className="mt-2 text-xs underline">Try again</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
