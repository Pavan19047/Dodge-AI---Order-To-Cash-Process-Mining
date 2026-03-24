// ---------------------------------------------------------------------------
// Graph types
// ---------------------------------------------------------------------------

export interface GraphNode {
  id: string            // "SalesOrder:12345"
  entity_type: string
  entity_id: string
  label: string
  properties: Record<string, unknown>
  // D3 simulation properties (added at runtime)
  x?: number
  y?: number
  vx?: number
  vy?: number
  fx?: number | null
  fy?: number | null
}

export interface GraphEdge {
  source: string | GraphNode
  target: string | GraphNode
  relationship: string
}

export interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphStats {
  total_nodes: number
  total_edges: number
  by_entity_type: Record<string, number>
  by_relationship: Record<string, number>
}

// ---------------------------------------------------------------------------
// Chat types
// ---------------------------------------------------------------------------

export interface HistoryItem {
  role: 'user' | 'assistant'
  content: string
}

export interface HighlightedEntity {
  type: string
  id: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  intent?: string
  sql?: string
  data?: Record<string, unknown>[]
  highlighted_entities?: HighlightedEntity[]
  timestamp: Date
  loading?: boolean
}
