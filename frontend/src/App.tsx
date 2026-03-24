import { useState, useCallback } from "react";
import GraphCanvas from "./components/GraphCanvas";
import NodeDetailPanel from "./components/NodeDetailPanel";
import ChatPanel from "./components/ChatPanel";
import GraphControls from "./components/GraphControls";
import { EntityFilter } from "./components/GraphControls";
import { useGraph } from "./hooks/useGraph";
import { useChat } from "./hooks/useChat";
import type { GraphNode, HighlightedEntity } from "./types";
import { graphApi } from "./services/api";

export default function App() {
  const graph = useGraph();
  const chat = useChat();
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [activeFilterTypes, setActiveFilterTypes] = useState<Set<string>>(
    new Set(),
  );

  // ---------------------------------------------------------------------------
  // Node click / expand
  // ---------------------------------------------------------------------------
  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node);
  }, []);

  const handleNodeExpand = useCallback(
    (node: GraphNode) => {
      graph.expandNode(node);
    },
    [graph],
  );

  // ---------------------------------------------------------------------------
  // Trace from detail panel
  // ---------------------------------------------------------------------------
  const handleTrace = useCallback(
    async (node: GraphNode) => {
      try {
        const result = await graphApi.trace(node.entity_type, node.entity_id);
        graph.mergeGraph(result.nodes, result.edges);
        setSelectedNode(null);
      } catch (e) {
        console.error("Trace failed", e);
      }
    },
    [graph],
  );

  // ---------------------------------------------------------------------------
  // Chat → graph highlight
  // ---------------------------------------------------------------------------
  const handleHighlight = useCallback(
    (entities: HighlightedEntity[]) => {
      graph.highlightEntities(entities);
    },
    [graph],
  );

  // ---------------------------------------------------------------------------
  // Entity filter
  // ---------------------------------------------------------------------------
  const handleToggleType = useCallback((type: string) => {
    setActiveFilterTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  const handleApplyFilter = useCallback(
    (types: string[]) => {
      graph.filterByTypes(types);
    },
    [graph],
  );

  const handleClearFilter = useCallback(() => {
    setActiveFilterTypes(new Set());
    graph.reload();
  }, [graph]);

  return (
    <div
      className="flex flex-col h-screen w-screen overflow-hidden"
      style={{ background: "#0a0f1a", color: "#f1f5f9" }}
    >
      {/* ------------------------------------------------------------------ */}
      {/* Header                                                               */}
      {/* ------------------------------------------------------------------ */}
      <header
        className="shrink-0 flex items-center justify-between px-6 h-12"
        style={{
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          background: "rgba(5,8,16,0.8)",
        }}
      >
        <div className="flex items-center gap-3">
          <div className="flex gap-0.5">
            <div className="w-1.5 h-5 rounded-sm bg-indigo-500" />
            <div className="w-1.5 h-5 rounded-sm bg-cyan-400" />
            <div className="w-1.5 h-3 mt-1 rounded-sm bg-violet-500" />
          </div>
          <span className="font-bold text-base tracking-tight text-slate-100">
            Dodge<span className="text-indigo-400"> AI</span>
          </span>
          <span className="text-slate-600 text-xs hidden md:block">
            Order-to-Cash Process Mining
          </span>
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-600">
          {graph.loading && (
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
              Loading graph…
            </span>
          )}
          {graph.error && (
            <span className="text-red-500 text-xs">{graph.error}</span>
          )}
          <span>DuckDB · Gemini 2.0</span>
        </div>
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Main layout                                                          */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex flex-1 overflow-hidden">
        {/* Graph pane — 65% */}
        <div
          className="relative flex-[65]"
          style={{ borderRight: "1px solid rgba(255,255,255,0.06)" }}
        >
          {/* Canvas */}
          <GraphCanvas
            nodes={graph.nodes}
            edges={graph.edges}
            highlightedIds={graph.highlightedIds}
            onNodeClick={handleNodeClick}
            onNodeExpand={handleNodeExpand}
          />

          {/* Top-right controls bar */}
          <GraphControls
            stats={graph.stats}
            onReset={graph.reload}
            nodeCount={graph.nodes.length}
            edgeCount={graph.edges.length}
          />

          {/* Bottom-left entity filter */}
          <EntityFilter
            activeTypes={activeFilterTypes}
            onToggle={handleToggleType}
            onApply={handleApplyFilter}
            onClear={handleClearFilter}
          />

          {/* Node detail panel */}
          <NodeDetailPanel
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
            onTrace={handleTrace}
          />

          {/* Empty state */}
          {!graph.loading && graph.nodes.length === 0 && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-slate-600">
              <div className="text-5xl opacity-20">⬡</div>
              <p className="text-sm">
                No graph data — add CSVs to backend/data/
              </p>
              <button
                onClick={graph.reload}
                className="text-xs text-slate-500 hover:text-slate-300 underline"
              >
                Retry
              </button>
            </div>
          )}
        </div>

        {/* Chat pane — 35% */}
        <div className="flex-[35] flex flex-col overflow-hidden min-w-[320px]">
          <ChatPanel
            messages={chat.messages}
            loading={chat.loading}
            onSend={chat.sendMessage}
            onHighlight={handleHighlight}
            onClear={chat.clearHistory}
          />
        </div>
      </div>
    </div>
  );
}
