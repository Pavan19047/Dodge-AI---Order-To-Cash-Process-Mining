import { useState, useEffect, useCallback, useRef } from 'react'
import { graphApi } from '../services/api'
import type { GraphNode, GraphEdge, GraphStats, HighlightedEntity } from '../types'

interface GraphState {
  nodes: GraphNode[]
  edges: GraphEdge[]
  stats: GraphStats | null
  loading: boolean
  error: string | null
  highlightedIds: Set<string>   // node IDs to pulse-highlight (from chat)
}

export function useGraph() {
  const [state, setState] = useState<GraphState>({
    nodes: [],
    edges: [],
    stats: null,
    loading: true,
    error: null,
    highlightedIds: new Set(),
  })

  // Track expanded node IDs so we don't re-expand
  const expandedRef = useRef<Set<string>>(new Set())

  // ---------------------------------------------------------------------------
  // Initial load
  // ---------------------------------------------------------------------------
  const loadOverview = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const [overview, stats] = await Promise.all([
        graphApi.overview(250),
        graphApi.stats(),
      ])
      setState((s) => ({
        ...s,
        nodes: overview.nodes,
        edges: overview.edges,
        stats,
        loading: false,
      }))
    } catch (err) {
      setState((s) => ({
        ...s,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to load graph',
      }))
    }
  }, [])

  useEffect(() => {
    loadOverview()
  }, [loadOverview])

  // ---------------------------------------------------------------------------
  // Expand a node — fetch its 1-hop neighbours and merge
  // ---------------------------------------------------------------------------
  const expandNode = useCallback(async (node: GraphNode) => {
    if (expandedRef.current.has(node.id)) return
    expandedRef.current.add(node.id)

    try {
      const result = await graphApi.neighbors(node.entity_type, node.entity_id)

      setState((prev) => {
        const existingIds = new Set(prev.nodes.map((n) => n.id))
        const newNodes = result.nodes.filter((n) => !existingIds.has(n.id))

        const existingEdgeKeys = new Set(
          prev.edges.map((e) => {
            const src = typeof e.source === 'string' ? e.source : e.source.id
            const tgt = typeof e.target === 'string' ? e.target : e.target.id
            return `${src}→${tgt}→${e.relationship}`
          }),
        )
        const newEdges = result.edges.filter((e) => {
          const src = typeof e.source === 'string' ? e.source : (e.source as GraphNode).id
          const tgt = typeof e.target === 'string' ? e.target : (e.target as GraphNode).id
          return !existingEdgeKeys.has(`${src}→${tgt}→${e.relationship}`)
        })

        return {
          ...prev,
          nodes: [...prev.nodes, ...newNodes],
          edges: [...prev.edges, ...newEdges],
        }
      })
    } catch {
      // Silently ignore expansion errors
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Highlight entities surfaced by the chat
  // ---------------------------------------------------------------------------
  const highlightEntities = useCallback((entities: HighlightedEntity[]) => {
    const ids = new Set(entities.map((e) => `${e.type}:${e.id}`))
    setState((s) => ({ ...s, highlightedIds: ids }))
    // Auto-clear highlights after 8 s
    setTimeout(() => {
      setState((s) => ({ ...s, highlightedIds: new Set() }))
    }, 8000)
  }, [])

  // ---------------------------------------------------------------------------
  // Filter by entity types
  // ---------------------------------------------------------------------------
  const filterByTypes = useCallback(async (types: string[]) => {
    setState((s) => ({ ...s, loading: true }))
    try {
      const result = await graphApi.filter(types.length ? types : undefined, 150)
      expandedRef.current.clear()
      setState((s) => ({
        ...s,
        nodes: result.nodes,
        edges: result.edges,
        loading: false,
      }))
    } catch {
      setState((s) => ({ ...s, loading: false }))
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Merge an external subgraph (e.g. from a trace response)
  // ---------------------------------------------------------------------------
  const mergeGraph = useCallback((newNodes: GraphNode[], newEdges: GraphEdge[]) => {
    setState((prev) => {
      const existingIds = new Set(prev.nodes.map((n) => n.id))
      const mergedNodes = [...prev.nodes, ...newNodes.filter((n) => !existingIds.has(n.id))]
      const allNodeIds = new Set(mergedNodes.map((n) => n.id))

      const existingEdgeKeys = new Set(
        prev.edges.map((e) => {
          const src = typeof e.source === 'string' ? e.source : (e.source as GraphNode).id
          const tgt = typeof e.target === 'string' ? e.target : (e.target as GraphNode).id
          return `${src}→${tgt}→${e.relationship}`
        }),
      )
      const mergedEdges = [
        ...prev.edges,
        ...newEdges.filter((e) => {
          const src = typeof e.source === 'string' ? e.source : (e.source as GraphNode).id
          const tgt = typeof e.target === 'string' ? e.target : (e.target as GraphNode).id
          // Drop edges where either endpoint is missing from the merged node set
          return (
            allNodeIds.has(src) &&
            allNodeIds.has(tgt) &&
            !existingEdgeKeys.has(`${src}→${tgt}→${e.relationship}`)
          )
        }),
      ]

      return { ...prev, nodes: mergedNodes, edges: mergedEdges }
    })
  }, [])

  const reset = useCallback(() => {
    expandedRef.current.clear()
    loadOverview()
  }, [loadOverview])

  return {
    ...state,
    expandNode,
    mergeGraph,
    highlightEntities,
    filterByTypes,
    reset,
    reload: loadOverview,
  }
}
