import type { GraphStats } from "../types";
import { ENTITY_COLORS } from "../utils/colors";

interface GraphControlsProps {
  stats: GraphStats | null;
  onReset: () => void;
  nodeCount: number;
  edgeCount: number;
}

export default function GraphControls({
  stats,
  onReset,
  nodeCount,
  edgeCount,
}: GraphControlsProps) {
  return (
    <div
      className="absolute top-4 right-4 z-20 rounded-xl px-4 py-3 flex items-center gap-4"
      style={{
        background: "rgba(10,15,26,0.9)",
        border: "1px solid rgba(255,255,255,0.08)",
        backdropFilter: "blur(8px)",
      }}
    >
      {/* Node / Edge counts */}
      <div className="flex items-center gap-3 text-[11px]">
        <span className="text-slate-400">
          <span className="text-slate-200 font-semibold">{nodeCount}</span>{" "}
          nodes
        </span>
        <span className="text-slate-700">·</span>
        <span className="text-slate-400">
          <span className="text-slate-200 font-semibold">{edgeCount}</span>{" "}
          edges
        </span>
        {stats && (
          <>
            <span className="text-slate-700">·</span>
            <span className="text-slate-400">
              <span className="text-slate-200 font-semibold">
                {stats.total_nodes}
              </span>{" "}
              total
            </span>
          </>
        )}
      </div>

      {/* Divider */}
      <div className="w-px h-4 bg-slate-700" />

      {/* Reset */}
      <button
        onClick={onReset}
        className="text-[11px] text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1"
      >
        <span>↺</span>
        Reset
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Entity type filter (separate component)
// ---------------------------------------------------------------------------
interface EntityFilterProps {
  activeTypes: Set<string>;
  onToggle: (type: string) => void;
  onApply: (types: string[]) => void;
  onClear: () => void;
}

export function EntityFilter({
  activeTypes,
  onToggle,
  onApply,
  onClear,
}: EntityFilterProps) {
  const allTypes = Object.keys(ENTITY_COLORS);

  return (
    <div
      className="absolute bottom-4 left-4 z-20 rounded-xl overflow-hidden"
      style={{
        background: "rgba(10,15,26,0.92)",
        border: "1px solid rgba(255,255,255,0.08)",
        backdropFilter: "blur(8px)",
      }}
    >
      <div
        className="px-3 py-1.5 text-[9px] font-semibold uppercase tracking-widest text-slate-500 flex items-center justify-between"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <span>Entity Types</span>
        <button
          onClick={onClear}
          className="text-slate-600 hover:text-slate-400 transition-colors normal-case tracking-normal"
        >
          clear
        </button>
      </div>
      <div className="px-2 py-2 space-y-0.5">
        {allTypes.map((type) => {
          const color = ENTITY_COLORS[type];
          const active = activeTypes.has(type);
          return (
            <button
              key={type}
              onClick={() => onToggle(type)}
              className="w-full flex items-center gap-2 px-2 py-1 rounded-lg text-left transition-all"
              style={{
                background: active ? `${color}18` : "transparent",
              }}
            >
              <div
                className="w-2 h-2 rounded-full shrink-0 transition-opacity"
                style={{
                  background: color,
                  opacity: active ? 1 : 0.3,
                }}
              />
              <span
                className="text-[11px] transition-colors"
                style={{
                  color: active ? "rgb(203,213,225)" : "rgb(100,116,139)",
                }}
              >
                {type}
              </span>
            </button>
          );
        })}
      </div>
      <div
        className="px-3 pb-2 pt-1"
        style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}
      >
        <button
          onClick={() => onApply(Array.from(activeTypes))}
          disabled={activeTypes.size === 0}
          className="w-full py-1.5 rounded-lg text-[10px] font-semibold transition-all disabled:opacity-40"
          style={{
            background: "rgba(99,102,241,0.25)",
            border: "1px solid rgba(99,102,241,0.4)",
            color: "#a5b4fc",
          }}
        >
          Apply Filter
        </button>
      </div>
    </div>
  );
}
