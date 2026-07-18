import { useState, useEffect, FormEvent } from "react";
import { askQuestion, getStats, AskResponse, Stats } from "./api";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: AskResponse["sources"];
  retrievalHit?: boolean;
}

const SAMPLE_QUESTIONS = [
  "Should I pay the ambulance bill myself?",
  "Am I covered if I get sick in Jamaica?",
  "Can my grandchild be added to my plan?",
  "Does MASA cover a private hospital room?",
];

function App() {
  const [view, setView] = useState<"chat" | "stats">("chat");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);

  useEffect(() => {
    if (view === "stats") {
      getStats()
        .then(setStats)
        .catch(() => setStatsError("Couldn't load stats — is the backend running?"));
    }
  }, [view]);

  async function handleAsk(query: string) {
    if (!query.trim() || loading) return;
    setMessages((m) => [...m, { role: "user", content: query }]);
    setInput("");
    setLoading(true);
    try {
      const res = await askQuestion(query);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: res.answer, sources: res.sources, retrievalHit: res.retrieval_hit },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "Something went wrong reaching the backend. Is it running?" },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    handleAsk(input);
  }

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <div>
            <div className="brand-title">Coverage Copilot</div>
            <div className="brand-sub">RAG-powered assistant for MASA's public FAQ &amp; benefits pages</div>
          </div>
        </div>
        <nav className="tabs">
          <button className={view === "chat" ? "tab active" : "tab"} onClick={() => setView("chat")}>
            Chat
          </button>
          <button className={view === "stats" ? "tab active" : "tab"} onClick={() => setView("stats")}>
            Dashboard
          </button>
        </nav>
      </header>

      {view === "chat" ? (
        <main className="chat-area">
          {messages.length === 0 && (
            <div className="empty-state">
              <p>Ask a question about MASA membership coverage.</p>
              <div className="samples">
                {SAMPLE_QUESTIONS.map((q) => (
                  <button key={q} className="sample-chip" onClick={() => handleAsk(q)}>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="messages">
            {messages.map((m, i) => (
              <div key={i} className={`bubble ${m.role}`}>
                <div className="bubble-content">{m.content}</div>
                {m.role === "assistant" && m.sources && m.sources.length > 0 && (
                  <div className="sources">
                    <span className="sources-label">
                      {m.retrievalHit ? "Sourced from:" : "No confident match found in knowledge base"}
                    </span>
                    {m.retrievalHit &&
                      m.sources.map((s, j) => (
                        <span className="source-pill" key={j} title={s.source_url}>
                          {s.heading} · {(s.similarity * 100).toFixed(0)}%
                        </span>
                      ))}
                  </div>
                )}
              </div>
            ))}
            {loading && <div className="bubble assistant loading">Thinking…</div>}
          </div>

          <form className="composer" onSubmit={onSubmit}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about coverage, claims, travel protection…"
            />
            <button type="submit" disabled={loading}>
              Ask
            </button>
          </form>
        </main>
      ) : (
        <main className="stats-area">
          {statsError && <p className="error">{statsError}</p>}
          {!stats && !statsError && <p>Loading…</p>}
          {stats && (
            <div className="stat-grid">
              <div className="stat-card">
                <div className="stat-value">{stats.totals.total_queries}</div>
                <div className="stat-label">Total queries</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{Math.round(stats.totals.avg_latency_ms)}ms</div>
                <div className="stat-label">Avg latency</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{(stats.totals.retrieval_hit_rate * 100).toFixed(0)}%</div>
                <div className="stat-label">Retrieval hit rate</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {stats.totals.total_input_tokens + stats.totals.total_output_tokens}
                </div>
                <div className="stat-label">Total tokens used</div>
              </div>
            </div>
          )}
        </main>
      )}
    </div>
  );
}

export default App;
