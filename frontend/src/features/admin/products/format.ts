const EVENT_LABELS: Record<string, string> = {
  'product.created': 'Created',
  'product.changed': 'Changed',
  'product.archived': 'Archived',
  'product.restored': 'Restored',
  'product.stock_decreased': 'Stock decreased',
}

const FIELD_LABELS: Record<string, string> = {
  sku: 'SKU',
  name: 'Name',
  description: 'Description',
  category: 'Category',
  price: 'Price',
  stock: 'Stock',
  weight_kg: 'Weight (kg)',
  tags: 'Tags',
  status: 'Status',
  quantity: 'Quantity',
  order_reference: 'Order',
}

export function formatPrice(price: string, currency: string): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(Number(price))
}

export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'medium',
    timeStyle: 'medium',
    timeZone: 'UTC',
  }).format(new Date(iso))
}

export function eventLabel(event: string): string {
  return EVENT_LABELS[event] ?? event
}

export function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field
}

export function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '(empty)'
  }
  if (Array.isArray(value)) {
    return value.length === 0 ? '(none)' : value.join(', ')
  }
  return String(value)
}
