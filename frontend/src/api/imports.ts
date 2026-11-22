import { request } from './client'

export type RowOutcome =
  'create' | 'update' | 'unchanged' | 'needs_review' | 'rejected' | 'superseded' | 'blank'

export type ImportStatus = 'PENDING_REVIEW' | 'COMMITTED' | 'DISCARDED' | 'EXPIRED'

export type RowAction = 'confirm' | 'correct' | 'skip'

export type ImportIssue = {
  field: string
  code: string
  severity: 'warning' | 'review' | 'error'
  message: string
  params: Record<string, unknown>
}

export type Resolution = {
  action: RowAction
  actor: string
  at: string
  before: Record<string, unknown>
  after: Record<string, unknown>
  original_issues: string[]
}

export type ImportRow = {
  line: number
  outcome: RowOutcome
  original_outcome: RowOutcome
  decision: 'confirmed' | 'skipped' | null
  pending: boolean
  applies: boolean
  editable: boolean
  actions: RowAction[]
  sku: string | null
  name: string | null
  issues: ImportIssue[]
  changes: Record<string, { before: string; after: string }>
  needs_confirmation: boolean
  superseded_by: number | null
  target_product_id: string | null
  values: Record<string, string>
  raw_values: Record<string, string>
  raw: string
  history: Resolution[]
}

export type ImportSummary = {
  id: string
  file_name: string
  sha256: string
  size_bytes: number
  status: ImportStatus
  uploaded_by: string
  uploaded_at: string
  expires_at: string
  finished_at: string | null
  rows: number
  summary: Record<RowOutcome, number>
  pending_lines: number[]
  committable: boolean
  result: { created?: number; updated?: number; skipped?: number }
  warnings: number
  file_warnings: ImportIssue[]
}

export type ImportBatch = ImportSummary & { items: ImportRow[] }

export type RowChange = { batch: ImportSummary; row: ImportRow }

export type RowValues = Partial<Record<string, string>>

export type Resolve =
  | { action: 'confirm'; expected_outcome: RowOutcome }
  | { action: 'skip' }
  | { action: 'correct'; values: RowValues }

const path = (id: string, suffix = '') => `/imports/${encodeURIComponent(id)}${suffix}`

export const importsApi = {
  upload: (file: File, actor: string) =>
    request<ImportBatch>('POST', '/imports', { file, actor, query: { file_name: file.name } }),
  get: (id: string) => request<ImportBatch>('GET', path(id)),
  resolve: (id: string, line: number, resolve: Resolve, actor: string) =>
    request<RowChange>('PATCH', path(id, `/rows/${line}`), { body: resolve, actor }),
  commit: (id: string, actor: string) =>
    request<ImportBatch>('POST', path(id, '/commit'), { actor }),
  discard: (id: string, actor: string) => request<ImportBatch>('DELETE', path(id), { actor }),
}
