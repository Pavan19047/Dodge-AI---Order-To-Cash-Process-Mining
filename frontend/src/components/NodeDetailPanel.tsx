import { useRef, useEffect } from "react";
import type { GraphNode } from "../types";
import { getNodeColor } from "../utils/colors";

interface Props {
  node: GraphNode | null;
  onClose: () => void;
  onTrace: (node: GraphNode) => void;
}

export default function NodeDetailPanel({ node, onClose, onTrace }: Props) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  if (!node) return null;

  const color = getNodeColor(node.entity_type);
  const props = node.properties ?? {};
  const propEntries = Object.entries(props).filter(
    ([k]) => !["id", "entity_id", "entity_type"].includes(k),
  );

  return (
    <div
      ref={panelRef}
      className="absolute top-4 left-4 z-30 w-72 rounded-xl shadow-2xl overflow-hidden"
      style={{
        background: "rgba(10,15,26,0.97)",
        border: `1px solid ${color}44`,
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: `1px solid ${color}33` }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-2.5 h-2.5 rounded-full"
            style={{ background: color }}
          />
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
            {node.entity_type}
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-slate-500 hover:text-slate-300 text-lg leading-none"
        >
          ×
        </button>
      </div>

      {/* Entity ID */}
      <div className="px-4 pt-3 pb-2">
        <p className="text-xs text-slate-500 mb-0.5">ID</p>
        <p
          className="text-sm font-mono font-semibold break-all"
          style={{ color }}
        >
          {node.entity_id}
        </p>
        {node.label && node.label !== node.entity_id && (
          <>
            <p className="text-xs text-slate-500 mt-2 mb-0.5">Label</p>
            <p className="text-sm text-slate-200">{node.label}</p>
          </>
        )}
      </div>

      {/* Properties */}
      {propEntries.length > 0 && (
        <div
          className="mx-4 mb-3 rounded-lg overflow-hidden"
          style={{ border: "1px solid rgba(255,255,255,0.06)" }}
        >
          <div className="px-3 py-1.5 text-[10px] uppercase tracking-widest text-slate-500 bg-white/[0.02]">
            Properties
          </div>
          <div className="divide-y divide-white/[0.04]">
            {propEntries.slice(0, 12).map(([key, val]) => (
              <div key={key} className="flex items-start px-3 py-1.5 gap-2">
                <span className="text-[10px] text-slate-500 w-28 shrink-0 pt-0.5 truncate">
                  {key}
                </span>
                <span className="text-[11px] text-slate-300 break-all">
                  {String(val ?? "—")}
                </span>
              </div>
            ))}
            {propEntries.length > 12 && (
              <div className="px-3 py-1.5 text-[10px] text-slate-600">
                +{propEntries.length - 12} more properties
              </div>
            )}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="px-4 pb-4">
        <button
          onClick={() => onTrace(node)}
          className="w-full py-2 rounded-lg text-xs font-semibold transition-all"
          style={{
            background: `${color}22`,
            border: `1px solid ${color}55`,
            color,
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.background = `${color}40`)
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.background = `${color}22`)
          }
        >
          Trace Full Flow
        </button>
      </div>
    </div>
  );
}
