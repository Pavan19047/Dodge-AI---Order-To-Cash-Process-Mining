import { useState, useCallback } from 'react'
import { chatApi } from '../services/api'
import type { ChatMessage, HistoryItem, HighlightedEntity } from '../types'

interface UseChatReturn {
  messages: ChatMessage[]
  loading: boolean
  sendMessage: (text: string) => Promise<HighlightedEntity[]>
  clearHistory: () => void
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        "Welcome to **Dodge AI — Order-to-Cash Explorer**. Ask me anything about the dataset, for example:\n\n" +
        "- *Which customers have the most sales orders?*\n" +
        "- *Find sales orders without deliveries*\n" +
        "- *Trace the full flow for billing document 90001234*\n" +
        "- *What materials appear most often in billing documents?*",
      timestamp: new Date(),
    },
  ])
  const [loading, setLoading] = useState(false)

  const sendMessage = useCallback(
    async (text: string): Promise<HighlightedEntity[]> => {
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: text,
        timestamp: new Date(),
      }

      const placeholderId = crypto.randomUUID()
      const placeholder: ChatMessage = {
        id: placeholderId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        loading: true,
      }

      setMessages((prev) => [...prev, userMsg, placeholder])
      setLoading(true)

      // Build history (last 6 messages for context window)
      const history: HistoryItem[] = messages
        .filter((m) => !m.loading && m.id !== 'welcome')
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content }))

      try {
        const response = await chatApi.send(text, history)
        const assistantMsg: ChatMessage = {
          id: placeholderId,
          role: 'assistant',
          content: response.message,
          intent: response.intent,
          sql: response.sql ?? undefined,
          data: response.data ?? undefined,
          highlighted_entities: response.highlighted_entities ?? [],
          timestamp: new Date(),
          loading: false,
        }
        setMessages((prev) =>
          prev.map((m) => (m.id === placeholderId ? assistantMsg : m)),
        )
        return response.highlighted_entities ?? []
      } catch (err) {
        const errorMsg: ChatMessage = {
          id: placeholderId,
          role: 'assistant',
          content: `⚠️ Error: ${err instanceof Error ? err.message : 'Could not reach the server. Make sure the backend is running.'}`,
          timestamp: new Date(),
          loading: false,
        }
        setMessages((prev) =>
          prev.map((m) => (m.id === placeholderId ? errorMsg : m)),
        )
        return []
      } finally {
        setLoading(false)
      }
    },
    [messages],
  )

  const clearHistory = useCallback(() => {
    setMessages((prev) => prev.filter((m) => m.id === 'welcome'))
  }, [])

  return { messages, loading, sendMessage, clearHistory }
}
