const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export interface Source {
  heading: string;
  source_url: string;
  similarity: number;
}

export interface AskResponse {
  answer: string;
  sources: Source[];
  retrieval_hit: boolean;
}

export async function askQuestion(query: string): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return res.json();
}

export interface Stats {
  totals: {
    total_queries: number;
    avg_latency_ms: number;
    retrieval_hit_rate: number;
    total_input_tokens: number;
    total_output_tokens: number;
  };
  recent_hourly: { bucket: string; n: number }[];
}

export async function getStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return res.json();
}
