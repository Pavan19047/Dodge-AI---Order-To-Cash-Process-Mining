import * as d3 from 'd3'
import type { GraphNode, GraphEdge } from '../types'

export const NODE_RADII: Record<string, number> = {
  SalesOrder: 14,
  SalesOrderItem: 9,
  Delivery: 13,
  DeliveryItem: 8,
  BillingDocument: 12,
  BillingDocumentItem: 8,
  JournalEntry: 11,
  Customer: 15,
  Material: 11,
  Plant: 10,
}

export const DEFAULT_RADIUS = 9

export function getNodeRadius(node: GraphNode, connectionCount?: number): number {
  const base = NODE_RADII[node.entity_type] ?? DEFAULT_RADIUS
  if (connectionCount !== undefined && connectionCount > 5) {
    return base + Math.min(Math.sqrt(connectionCount) * 1.5, 8)
  }
  return base
}

export function createForceSimulation(
  nodes: GraphNode[],
  edges: GraphEdge[],
  width: number,
  height: number,
) {
  return d3
    .forceSimulation<GraphNode>(nodes)
    .force(
      'link',
      d3
        .forceLink<GraphNode, GraphEdge>(edges)
        .id((d) => d.id)
        .distance(90)
        .strength(0.4),
    )
    .force('charge', d3.forceManyBody<GraphNode>().strength(-250))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force(
      'collision',
      d3.forceCollide<GraphNode>().radius((d) => getNodeRadius(d) + 4),
    )
    .force('x', d3.forceX(width / 2).strength(0.04))
    .force('y', d3.forceY(height / 2).strength(0.04))
    .alphaDecay(0.025)
}
