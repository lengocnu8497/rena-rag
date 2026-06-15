const API = '/api';

export interface EvalLog {
  id: string;
  created_at: string;
  query: string;
  intent: string | null;
  pipeline_mode: string | null;
  mean_retrieval_score: number | null;
  faithfulness_score: number | null;
  latency_ms: number | null;
  cost_usd: number | null;
  scope_blocked: boolean;
  model_generation: string | null;
  tokens_input: number | null;
  tokens_output: number | null;
  retrieved_sources: string[] | null;
}

export interface Chunk {
  id: string;
  source_type: string;
  source_name: string;
  section: string | null;
  procedure_tags: string[];
  paper_year: number | null;
  content: string;
  created_at: string;
}

export interface ChunkItem {
  id: string;
  source_name: string;
  section: string | null;
  procedure_tags: string[];
  content: string;
  similarity: number;
}

export interface RouteInfo {
  in_scope: boolean;
  pipeline: string;
  intent: string;
  procedure_tags: string[];
  sections: string[];
  source_type: string | null;
  rewrite: string | null;
}

export interface InspectResult {
  query: string;
  rewritten_query: string;
  route: RouteInfo;
  retrieved_chunks: ChunkItem[];
  reranked_chunks: ChunkItem[];
  response: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
}

export interface CostRow {
  date: string;
  sonnet_cost: number;
  haiku_cost: number;
  embed_cost: number;
  total_cost: number;
  requests: number;
  mean_latency_ms: number;
}

export interface ChunkStats {
  total: number;
  by_source: Record<string, number>;
  by_section: Record<string, number>;
  by_procedure: Record<string, number>;
}

async function get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const url = new URL(API + path, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) url.searchParams.set(k, String(v));
    }
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function del(path: string): Promise<void> {
  const res = await fetch(API + path, { method: 'DELETE' });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}

export const api = {
  evalLogs: (p: {
    limit?: number;
    offset?: number;
    intent?: string;
    pipeline_mode?: string;
    date_from?: string;
    date_to?: string;
    scope_blocked?: boolean;
  }) => get<{ data: EvalLog[]; limit: number; offset: number }>('/eval-logs', p as Record<string, string | number | boolean | undefined>),

  chunks: (p: {
    limit?: number;
    offset?: number;
    procedure?: string;
    section?: string;
    source_type?: string;
    search?: string;
  }) => get<{ data: Chunk[]; limit: number; offset: number }>('/chunks', p as Record<string, string | number | boolean | undefined>),

  deleteChunk: (id: string) => del(`/chunks/${id}`),

  inspect: (query: string) => post<InspectResult>('/inspect', { query }),

  costSummary: (days?: number) => get<{ data: CostRow[] }>('/cost-summary', days ? { days } : undefined),

  chunkStats: () => get<ChunkStats>('/chunk-stats'),
};
