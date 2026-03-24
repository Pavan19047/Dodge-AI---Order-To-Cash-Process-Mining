export const ENTITY_COLORS: Record<string, string> = {
  SalesOrder: '#3b82f6',
  SalesOrderItem: '#60a5fa',
  Delivery: '#10b981',
  DeliveryItem: '#34d399',
  BillingDocument: '#f59e0b',
  BillingDocumentItem: '#fbbf24',
  JournalEntry: '#ef4444',
  Customer: '#8b5cf6',
  Material: '#ec4899',
  Plant: '#6366f1',
}

export const DEFAULT_NODE_COLOR = '#94a3b8'

export function getNodeColor(entityType: string): string {
  return ENTITY_COLORS[entityType] ?? DEFAULT_NODE_COLOR
}

export function getNodeColorWithAlpha(entityType: string, alpha: number): string {
  const hex = getNodeColor(entityType)
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}
