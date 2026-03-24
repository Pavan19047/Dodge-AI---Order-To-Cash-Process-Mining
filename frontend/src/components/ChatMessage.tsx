import { useState } from "react";
import type { ChatMessage as ChatMessageType } from "../types";

const INTENT_COLORS: Record<string, string> = {
  TRACE_FLOW: "#6366f1",
  AGGREGATION: "#22d3ee",
  ANOMALY_DETECTION: "#f59e0b",
  ENTITY_LOOKUP: "#34d399",
  RELATIONSHIP_QUERY: "#a78bfa",
  OFF_TOPIC: "#64748b",
};

interface Props {
  message: ChatMessageType;
}

export default function ChatMessage({ message }: Props) {
  const [sqlOpen, setSqlOpen] = useState(false);
  const [dataOpen, setDataOpen] = useState(false);

  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div
          className="max-w-[80%] px-4 py-2.5 rounded-2xl rounded-br-sm text-sm text-slate-100"
          style={{
            background: "rgba(99,102,241,0.25)",
            border: "1px solid rgba(99,102,241,0.4)",
          }}
        >
          {message.content}
        </div>
      </div>
    );
  }

  const intentColor = message.intent
    ? (INTENT_COLORS[message.intent] ?? "#64748b")
    : "#64748b";

  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] w-full">
        {/* Bubble */}
        <div
          className="px-4 py-3 rounded-2xl rounded-bl-sm text-sm"
          style={{
            background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          {/* Loading state */}
          {message.loading ? (
            <div className="flex items-center gap-1.5 text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:0ms]" />
              <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:150ms]" />
              <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:300ms]" />
            </div>
          ) : (
            <>
              {/* Intent badge */}
              {message.intent && message.intent !== "OFF_TOPIC" && (
                <div className="mb-2">
                  <span
                    className="text-[9px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full"
                    style={{
                      background: `${intentColor}22`,
                      color: intentColor,
                      border: `1px solid ${intentColor}44`,
                    }}
                  >
                    {message.intent.replace("_", " ")}
                  </span>
                </div>
              )}

              {/* Message text */}
              <div className="text-slate-200 leading-relaxed whitespace-pre-wrap">
                {renderText(message.content)}
              </div>

              {/* SQL collapsible */}
              {message.sql && (
                <div className="mt-3">
                  <button
                    onClick={() => setSqlOpen((v) => !v)}
                    className="flex items-center gap-1.5 text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    <span
                      className="transition-transform duration-200"
                      style={{
                        transform: sqlOpen ? "rotate(90deg)" : "rotate(0deg)",
                      }}
                    >
                      ▶
                    </span>
                    View SQL
                  </button>
                  {sqlOpen && (
                    <pre
                      className="mt-2 p-3 rounded-lg text-[10px] leading-relaxed overflow-x-auto text-cyan-300"
                      style={{
                        background: "rgba(0,0,0,0.4)",
                        border: "1px solid rgba(255,255,255,0.06)",
                        fontFamily: "JetBrains Mono, monospace",
                      }}
                    >
                      {message.sql}
                    </pre>
                  )}
                </div>
              )}

              {/* Data table collapsible */}
              {message.data && message.data.length > 0 && (
                <div className="mt-2">
                  <button
                    onClick={() => setDataOpen((v) => !v)}
                    className="flex items-center gap-1.5 text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    <span
                      className="transition-transform duration-200"
                      style={{
                        transform: dataOpen ? "rotate(90deg)" : "rotate(0deg)",
                      }}
                    >
                      ▶
                    </span>
                    View Data ({message.data.length} rows)
                  </button>
                  {dataOpen && (
                    <div
                      className="mt-2 rounded-lg overflow-x-auto"
                      style={{ border: "1px solid rgba(255,255,255,0.06)" }}
                    >
                      <DataTable rows={message.data} />
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function renderText(text: string) {
  // Bold: **text**
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="text-slate-100 font-semibold">
          {part.slice(2, -2)}
        </strong>
      );
    }
    // Bullet lines
    if (part.includes("\n")) {
      return part.split("\n").map((line, j) => {
        const trimmed = line.trimStart();
        if (trimmed.startsWith("- ") || trimmed.startsWith("• ")) {
          return (
            <div key={`${i}-${j}`} className="flex gap-1.5 mt-0.5">
              <span className="text-slate-500 shrink-0">•</span>
              <span>{trimmed.slice(2)}</span>
            </div>
          );
        }
        return line ? (
          <span key={`${i}-${j}`}>
            {line}
            <br />
          </span>
        ) : (
          <br key={`${i}-${j}`} />
        );
      });
    }
    return <span key={i}>{part}</span>;
  });
}

function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) return null;
  const cols = Object.keys(rows[0]);
  return (
    <table className="w-full text-[10px]">
      <thead>
        <tr style={{ background: "rgba(255,255,255,0.04)" }}>
          {cols.map((c) => (
            <th
              key={c}
              className="px-2 py-1.5 text-left text-slate-500 font-semibold whitespace-nowrap"
            >
              {c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.slice(0, 20).map((row, i) => (
          <tr
            key={i}
            className="border-t border-white/[0.04] hover:bg-white/[0.02]"
          >
            {cols.map((c) => (
              <td
                key={c}
                className="px-2 py-1.5 text-slate-300 whitespace-nowrap max-w-[120px] truncate"
              >
                {String(row[c] ?? "")}
              </td>
            ))}
          </tr>
        ))}
        {rows.length > 20 && (
          <tr className="border-t border-white/[0.04]">
            <td
              colSpan={cols.length}
              className="px-2 py-1.5 text-slate-600 text-center"
            >
              +{rows.length - 20} more rows
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}
