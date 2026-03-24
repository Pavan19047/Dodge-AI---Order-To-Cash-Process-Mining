import { useRef, useEffect, type KeyboardEvent } from "react";
import ChatMessage from "./ChatMessage";
import type {
  ChatMessage as ChatMessageType,
  HighlightedEntity,
} from "../types";

interface Props {
  messages: ChatMessageType[];
  loading: boolean;
  onSend: (text: string) => Promise<HighlightedEntity[]>;
  onHighlight: (entities: HighlightedEntity[]) => void;
  onClear: () => void;
}

export default function ChatPanel({
  messages,
  loading,
  onSend,
  onHighlight,
  onClear,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const text = inputRef.current?.value.trim();
    if (!text || loading) return;
    inputRef.current!.value = "";
    inputRef.current!.style.height = "auto";
    const entities = await onSend(text);
    if (entities?.length) onHighlight(entities);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  };

  return (
    <div
      className="flex flex-col h-full"
      style={{ background: "rgba(5,8,16,0.6)" }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 shrink-0"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-sm font-semibold text-slate-200">Dodge AI</span>
          <span className="text-[10px] text-slate-500 ml-1">
            Gemini · DuckDB · Process Mining
          </span>
        </div>
        <button
          onClick={onClear}
          className="text-[10px] text-slate-600 hover:text-slate-400 transition-colors"
        >
          Clear
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 scrollbar-thin">
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions (shown when only welcome message) */}
      {messages.length === 1 && (
        <div className="px-4 pb-2 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => {
                if (inputRef.current) {
                  inputRef.current.value = s;
                  handleSend();
                }
              }}
              className="text-[10px] px-2.5 py-1.5 rounded-full text-slate-400 hover:text-slate-200 transition-colors"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.08)",
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div
        className="px-4 pb-4 pt-3 shrink-0"
        style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div
          className="flex items-end gap-2 rounded-xl px-3 py-2"
          style={{
            background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.12)",
          }}
        >
          <textarea
            ref={inputRef}
            rows={1}
            placeholder="Ask about orders, deliveries, anomalies…"
            className="flex-1 bg-transparent text-sm text-slate-200 placeholder-slate-600 resize-none outline-none leading-relaxed"
            style={{ maxHeight: 120 }}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            disabled={loading}
          />
          <button
            onClick={handleSend}
            disabled={loading}
            className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all"
            style={{
              background: loading
                ? "rgba(99,102,241,0.2)"
                : "rgba(99,102,241,0.7)",
              border: "1px solid rgba(99,102,241,0.5)",
            }}
          >
            {loading ? (
              <span className="w-3 h-3 border-2 border-indigo-300 border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg viewBox="0 0 16 16" className="w-4 h-4 fill-indigo-100">
                <path d="M2 8l12-6-4 6 4 6z" />
              </svg>
            )}
          </button>
        </div>
        <p className="text-[9px] text-slate-700 mt-1.5 text-center">
          Enter to send · Shift+Enter for newline
        </p>
      </div>
    </div>
  );
}

const SUGGESTIONS = [
  "Show top 10 customers by revenue",
  "Trace order 1000012",
  "Find overdue deliveries",
  "Which materials have the highest order volume?",
];
