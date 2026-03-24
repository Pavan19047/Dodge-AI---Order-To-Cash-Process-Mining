import { useEffect, useRef, useCallback, useState } from "react";
import * as d3 from "d3";
import type { GraphNode, GraphEdge } from "../types";
import { getNodeColor, getNodeColorWithAlpha } from "../utils/colors";
import { getNodeRadius, createForceSimulation } from "../utils/graphLayout";

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  highlightedIds: Set<string>;
  onNodeClick: (node: GraphNode) => void;
  onNodeExpand: (node: GraphNode) => void;
}

interface Tooltip {
  visible: boolean;
  x: number;
  y: number;
  node: GraphNode | null;
}

export default function GraphCanvas({
  nodes,
  edges,
  highlightedIds,
  onNodeClick,
  onNodeExpand,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphEdge> | null>(
    null,
  );
  const [tooltip, setTooltip] = useState<Tooltip>({
    visible: false,
    x: 0,
    y: 0,
    node: null,
  });

  // Connection count map for node sizing
  const connectionCounts = useRef<Map<string, number>>(new Map());

  // ---------------------------------------------------------------------------
  // Build connection counts
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const counts = new Map<string, number>();
    edges.forEach((e) => {
      const src =
        typeof e.source === "string" ? e.source : (e.source as GraphNode).id;
      const tgt =
        typeof e.target === "string" ? e.target : (e.target as GraphNode).id;
      counts.set(src, (counts.get(src) ?? 0) + 1);
      counts.set(tgt, (counts.get(tgt) ?? 0) + 1);
    });
    connectionCounts.current = counts;
  }, [edges]);

  // ---------------------------------------------------------------------------
  // Main D3 render effect
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const svg = d3.select(svgRef.current!);
    const width = svgRef.current!.clientWidth || 800;
    const height = svgRef.current!.clientHeight || 600;

    svg.selectAll("*").remove();

    // Defs for glow filters
    const defs = svg.append("defs");

    // Standard glow
    const glow = defs.append("filter").attr("id", "glow");
    glow
      .append("feGaussianBlur")
      .attr("stdDeviation", "3")
      .attr("result", "blur");
    const glowMerge = glow.append("feMerge");
    glowMerge.append("feMergeNode").attr("in", "blur");
    glowMerge.append("feMergeNode").attr("in", "SourceGraphic");

    // Strong glow for highlighted nodes
    const pulseGlow = defs.append("filter").attr("id", "pulseGlow");
    pulseGlow
      .append("feGaussianBlur")
      .attr("stdDeviation", "6")
      .attr("result", "blur");
    const pulseGlowMerge = pulseGlow.append("feMerge");
    pulseGlowMerge.append("feMergeNode").attr("in", "blur");
    pulseGlowMerge.append("feMergeNode").attr("in", "SourceGraphic");

    // Arrow marker
    defs
      .append("marker")
      .attr("id", "arrow")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 20)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", "#475569");

    // Zoom container
    const g = svg.append("g").attr("class", "zoom-container");

    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });
    svg.call(zoom);

    // Deep-clone nodes/edges so D3 can mutate positions
    const simNodes: GraphNode[] = nodes.map((n) => ({ ...n }));
    const nodeMap = new Map(simNodes.map((n) => [n.id, n]));

    const simEdges: GraphEdge[] = edges
      .map((e) => ({
        ...e,
        source:
          typeof e.source === "string" ? e.source : (e.source as GraphNode).id,
        target:
          typeof e.target === "string" ? e.target : (e.target as GraphNode).id,
      }))
      .filter(
        (e) =>
          nodeMap.has(e.source as string) && nodeMap.has(e.target as string),
      );

    // ---------------------------------------------------------------------------
    // Edges
    // ---------------------------------------------------------------------------
    const link = g
      .append("g")
      .attr("class", "edges")
      .selectAll<SVGLineElement, GraphEdge>("line")
      .data(simEdges)
      .join("line")
      .attr("stroke", "#1e3a5f")
      .attr("stroke-width", 1.2)
      .attr("stroke-opacity", 0.6)
      .attr("marker-end", "url(#arrow)");

    // ---------------------------------------------------------------------------
    // Edge labels (relationship type — shown on hover via opacity)
    // ---------------------------------------------------------------------------
    const edgeLabel = g
      .append("g")
      .attr("class", "edge-labels")
      .selectAll<SVGTextElement, GraphEdge>("text")
      .data(simEdges)
      .join("text")
      .attr("font-size", 8)
      .attr("fill", "#64748b")
      .attr("text-anchor", "middle")
      .attr("pointer-events", "none")
      .attr("opacity", 0)
      .text((d) => d.relationship);

    // ---------------------------------------------------------------------------
    // Nodes
    // ---------------------------------------------------------------------------
    const nodeGroup = g
      .append("g")
      .attr("class", "nodes")
      .selectAll<SVGGElement, GraphNode>("g")
      .data(simNodes, (d) => d.id)
      .join("g")
      .attr("class", "node")
      .attr("cursor", "pointer");

    // Outer glow ring for highlighted nodes
    nodeGroup
      .append("circle")
      .attr("class", "highlight-ring")
      .attr(
        "r",
        (d) => getNodeRadius(d, connectionCounts.current.get(d.id)) + 6,
      )
      .attr("fill", "none")
      .attr("stroke", (d) =>
        highlightedIds.has(d.id) ? getNodeColor(d.entity_type) : "none",
      )
      .attr("stroke-width", 2)
      .attr("filter", "url(#pulseGlow)")
      .attr("opacity", (d) => (highlightedIds.has(d.id) ? 0.8 : 0));

    // Main circle
    nodeGroup
      .append("circle")
      .attr("class", "node-circle")
      .attr("r", (d) => getNodeRadius(d, connectionCounts.current.get(d.id)))
      .attr("fill", (d) => getNodeColorWithAlpha(d.entity_type, 0.85))
      .attr("stroke", (d) => getNodeColor(d.entity_type))
      .attr("stroke-width", (d) => (highlightedIds.has(d.id) ? 2.5 : 1.5))
      .attr("filter", (d) =>
        highlightedIds.has(d.id) ? "url(#pulseGlow)" : "url(#glow)",
      );

    // Node label
    nodeGroup
      .append("text")
      .attr("class", "node-label")
      .attr(
        "dy",
        (d) => getNodeRadius(d, connectionCounts.current.get(d.id)) + 12,
      )
      .attr("text-anchor", "middle")
      .attr("font-size", 9)
      .attr("fill", "#94a3b8")
      .attr("pointer-events", "none")
      .text((d) => {
        const label = d.label ?? d.entity_id;
        return label.length > 14 ? label.slice(0, 12) + "…" : label;
      });

    // ---------------------------------------------------------------------------
    // Interactions
    // ---------------------------------------------------------------------------
    nodeGroup
      .on("mouseenter", function (event: MouseEvent, d: GraphNode) {
        d3.select(this).select(".node-circle").attr("stroke-width", 3);
        // Show edge labels for adjacent edges
        edgeLabel.attr("opacity", (e) => {
          const src =
            typeof e.source === "string"
              ? e.source
              : (e.source as GraphNode).id;
          const tgt =
            typeof e.target === "string"
              ? e.target
              : (e.target as GraphNode).id;
          return src === d.id || tgt === d.id ? 0.9 : 0;
        });
        const rect = svgRef.current!.getBoundingClientRect();
        setTooltip({
          visible: true,
          x: event.clientX - rect.left + 12,
          y: event.clientY - rect.top - 8,
          node: d,
        });
      })
      .on("mousemove", function (event: MouseEvent) {
        const rect = svgRef.current!.getBoundingClientRect();
        setTooltip((t) => ({
          ...t,
          x: event.clientX - rect.left + 12,
          y: event.clientY - rect.top - 8,
        }));
      })
      .on("mouseleave", function () {
        d3.select(this).select(".node-circle").attr("stroke-width", 1.5);
        edgeLabel.attr("opacity", 0);
        setTooltip({ visible: false, x: 0, y: 0, node: null });
      })
      .on("click", (_event: MouseEvent, d: GraphNode) => {
        onNodeClick(d);
      })
      .on("dblclick", (_event: MouseEvent, d: GraphNode) => {
        onNodeExpand(d);
      });

    // Drag behaviour
    const drag = d3
      .drag<SVGGElement, GraphNode>()
      .on("start", (event, d) => {
        if (!event.active) simulationRef.current?.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) simulationRef.current?.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    nodeGroup.call(drag);

    // ---------------------------------------------------------------------------
    // Force simulation
    // ---------------------------------------------------------------------------
    const simulation = createForceSimulation(simNodes, simEdges, width, height);
    simulationRef.current = simulation;

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as GraphNode).x ?? 0)
        .attr("y1", (d) => (d.source as GraphNode).y ?? 0)
        .attr("x2", (d) => (d.target as GraphNode).x ?? 0)
        .attr("y2", (d) => (d.target as GraphNode).y ?? 0);

      edgeLabel
        .attr(
          "x",
          (d) =>
            (((d.source as GraphNode).x ?? 0) +
              ((d.target as GraphNode).x ?? 0)) /
            2,
        )
        .attr(
          "y",
          (d) =>
            (((d.source as GraphNode).y ?? 0) +
              ((d.target as GraphNode).y ?? 0)) /
            2,
        );

      nodeGroup.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    // Initial zoom to fit
    svg.call(
      zoom.transform,
      d3.zoomIdentity.translate(width * 0.1, height * 0.1).scale(0.85),
    );

    return () => {
      simulation.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, highlightedIds]);

  // ---------------------------------------------------------------------------
  // Zoom controls
  // ---------------------------------------------------------------------------
  const handleZoomIn = useCallback(() => {
    if (!svgRef.current) return;
    d3.select(svgRef.current)
      .transition()
      .call(
        d3.zoom<SVGSVGElement, unknown>().scaleBy as unknown as (
          selection: d3.Selection<SVGSVGElement, unknown, null, undefined>,
          k: number,
        ) => void,
        1.3,
      );
  }, []);

  const handleZoomOut = useCallback(() => {
    if (!svgRef.current) return;
    d3.select(svgRef.current)
      .transition()
      .call(
        d3.zoom<SVGSVGElement, unknown>().scaleBy as unknown as (
          selection: d3.Selection<SVGSVGElement, unknown, null, undefined>,
          k: number,
        ) => void,
        0.77,
      );
  }, []);

  return (
    <div className="relative w-full h-full">
      {/* SVG Canvas */}
      <svg
        ref={svgRef}
        className="w-full h-full"
        style={{ background: "transparent" }}
      />

      {/* Tooltip */}
      {tooltip.visible && tooltip.node && (
        <div
          className="pointer-events-none absolute z-20 px-3 py-2 rounded-lg text-xs shadow-xl"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            background: "rgba(10,15,26,0.95)",
            border: `1px solid ${getNodeColor(tooltip.node.entity_type)}`,
            maxWidth: 240,
          }}
        >
          <div
            className="font-semibold mb-0.5"
            style={{ color: getNodeColor(tooltip.node.entity_type) }}
          >
            {tooltip.node.entity_type}
          </div>
          <div className="text-slate-300">{tooltip.node.entity_id}</div>
          <div className="text-slate-500 mt-1 text-[10px]">
            Click to inspect · Double-click to expand
          </div>
        </div>
      )}

      {/* Zoom buttons */}
      <div className="absolute bottom-4 right-4 flex flex-col gap-1">
        <button
          onClick={handleZoomIn}
          className="w-8 h-8 rounded bg-dark-600 text-slate-300 hover:bg-dark-500 text-lg flex items-center justify-center border border-slate-700"
        >
          +
        </button>
        <button
          onClick={handleZoomOut}
          className="w-8 h-8 rounded bg-dark-600 text-slate-300 hover:bg-dark-500 text-lg flex items-center justify-center border border-slate-700"
        >
          −
        </button>
      </div>
    </div>
  );
}
