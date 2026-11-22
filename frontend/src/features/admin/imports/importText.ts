import type { ImportIssue, ImportRow, ImportStatus, RowOutcome } from '../../../api/imports'

export type RowTab = RowOutcome | 'skipped'

export type TabKey = RowTab | 'warnings'

export const ROW_TABS: { key: RowTab; label: string }[] = [
  { key: 'needs_review', label: 'Needs review' },
  { key: 'update', label: 'Updates' },
  { key: 'create', label: 'New' },
  { key: 'unchanged', label: 'Unchanged' },
  { key: 'skipped', label: 'Skipped' },
  { key: 'rejected', label: 'Rejected' },
  { key: 'superseded', label: 'Superseded' },
  { key: 'blank', label: 'Blank' },
]

export const COLUMNS: { key: string; label: string }[] = [
  { key: 'name', label: 'Name' },
  { key: 'sku', label: 'SKU' },
  { key: 'description', label: 'Description' },
  { key: 'category', label: 'Category' },
  { key: 'price', label: 'Price' },
  { key: 'stock', label: 'Stock' },
  { key: 'weight_kg', label: 'Weight (kg)' },
]

const COLUMN_LABELS: Record<string, string> = {
  ...Object.fromEntries(COLUMNS.map((column) => [column.key, column.label])),
  gift: 'Gift',
  status: 'Status',
  row: 'Row',
  file: 'File',
}

const STATUS_LABELS: Record<ImportStatus, string> = {
  PENDING_REVIEW: 'Waiting for review',
  COMMITTED: 'Imported',
  DISCARDED: 'Discarded',
  EXPIRED: 'Expired',
}

export function columnLabel(column: string): string {
  return COLUMN_LABELS[column] ?? column
}

export function statusLabel(status: ImportStatus): string {
  return STATUS_LABELS[status]
}

export function reviewCodes(row: ImportRow): string[] {
  return row.issues.filter((issue) => issue.severity === 'review').map((issue) => issue.code)
}

export function confirmLabel(row: ImportRow): string {
  if (row.outcome === 'update') {
    return 'Confirm update'
  }
  const codes = reviewCodes(row)
  if (codes.includes('zero_price') && codes.includes('zero_weight')) {
    return 'Confirm free gift with weight 0'
  }
  return codes.includes('zero_price') ? 'Confirm as free gift' : 'Confirm weight 0'
}

export function warningsOf(row: ImportRow): ImportIssue[] {
  return row.issues.filter((issue) => issue.severity === 'warning')
}

export function lineList(lines: number[]): string {
  return lines.join(', ')
}

export function isSkipped(row: ImportRow): boolean {
  return row.decision === 'skipped'
}

export function rowsInTab(items: ImportRow[], tab: RowTab): ImportRow[] {
  if (tab === 'skipped') {
    return items.filter(isSkipped)
  }
  return items.filter((row) => row.outcome === tab && !isSkipped(row))
}

export function firstTab(items: ImportRow[]): TabKey {
  const order: RowOutcome[] = ['needs_review', 'update', 'create']
  return order.find((key) => rowsInTab(items, key).length > 0) ?? 'create'
}
