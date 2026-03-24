import axios from 'axios'
import type {
  GraphResponse,
  GraphStats,
  GraphNode,
  HistoryItem,
} from '../types'

const BASE = import.meta.env.VITE_API_URL ?? ''

const api = axios.create({
  baseURL: BASE,
  timeout: 60_000,
})

// ---------------------------------------------------------------------------
// Graph API
// ---------------------------------------------------------------------------

export const graphApi = {
  overview: (limit = 250): Promise<GraphResponse> =>
    api.get(`/api/graph/overview?limit=${limit}`).then((r) => r.data),

  stats: (): Promise<GraphStats> =>
    api.get('/api/graph/stats').then((r) => r.data),

  node: (entityType: string, entityId: string): Promise<GraphNode> =>
    api.get(`/api/graph/node/${entityType}/${entityId}`).then((r) => r.data),

  neighbors: (entityType: string, entityId: string): Promise<GraphResponse> =>
    api
      .get(`/api/graph/neighbors/${entityType}/${entityId}`)
      .then((r) => r.data),

  trace: (entityType: string, entityId: string): Promise<GraphResponse> =>
    api
      .get(`/api/graph/trace/${entityType}/${entityId}`)
      .then((r) => r.data),

  filter: (types?: string[], limit = 100): Promise<GraphResponse> => {
    const params = new URLSearchParams()
    if (types?.length) params.set('types', types.join(','))
    params.set('limit', String(limit))
    return api.get(`/api/graph/filter?${params}`).then((r) => r.data)
  },
}

// ---------------------------------------------------------------------------
// Chat API
// ---------------------------------------------------------------------------

export interface ChatAPIResponse {
  message: string
  intent?: string
  sql?: string
  data?: Record<string, unknown>[]
  highlighted_entities?: { type: string; id: string }[]
}

export const chatApi = {
  send: (
    message: string,
    history: HistoryItem[],
  ): Promise<ChatAPIResponse> =>
    api.post('/api/chat', { message, history }).then((r) => r.data),
}
