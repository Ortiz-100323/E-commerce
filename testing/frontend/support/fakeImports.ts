import { http, HttpResponse } from 'msw/http'

import type {
  ImportBatch,
  ImportIssue,
  ImportRow,
  ImportSummary,
  RowOutcome,
} from '../../../frontend/src/api/imports'
import { API, problem, validationProblem } from './api'
import { server } from './server'

export const IMPORT_ID = '7f1c2d3e-0000-4000-8000-0000000000aa'

const OUTCOMES: RowOutcome[] = [
  'create',
  'update',
  'unchanged',
  'needs_review',
  'rejected',
  'superseded',
  'blank',
]

type Upload = {
  contentType: string | null
  actor: string | null
  fileName: string | null
  body: string
}
type Resolution = { line: number; actor: string | null; body: Record<string, unknown> }

export function issue(
  field: string,
  code: string,
  severity: ImportIssue['severity'],
  message: string,
): ImportIssue {
  return { field, code, severity, message, params: {} }
}

export function importRow(line: number, outcome: RowOutcome, extra: Partial<ImportRow> = {}) {
  const sku = extra.sku ?? `SKU-${line}`
  const values = {
    name: `Product ${line}`,
    sku,
    description: 'A product',
    category: 'Misc',
    price: '10.00',
    stock: '5',
    weight_kg: '0.5',
    ...extra.values,
  }
  const row: ImportRow = {
    line,
    outcome,
    original_outcome: outcome,
    decision: null,
    pending: false,
    applies: outcome === 'create',
    editable: outcome === 'needs_review',
    actions: [],
    sku,
    name: values.name || null,
    issues: [],
    changes: {},
    needs_confirmation: false,
    superseded_by: null,
    target_product_id: null,
    values,
    raw_values: values,
    raw: Object.values(values).join(','),
    history: [],
    ...extra,
  }
  row.values = values
  row.raw_values = { ...values, ...extra.raw_values }
  row.pending =
    extra.pending ??
    (outcome === 'needs_review' || (outcome === 'update' && row.needs_confirmation))
  return row
}

export function reviewRow(line: number, code: string, field: string, values = {}) {
  const messages: Record<string, string> = {
    zero_price: 'The price is 0. Confirm the product as a free gift, or correct the price.',
    zero_weight: 'The weight is 0. Confirm the product has no physical weight, or correct it.',
    empty_required_field: `The ${field} is empty.`,
  }
  const confirmable = code !== 'empty_required_field'
  return importRow(line, 'needs_review', {
    values,
    issues: [issue(field, code, 'review', messages[code])],
    actions: confirmable ? ['confirm', 'correct', 'skip'] : ['correct', 'skip'],
  })
}

export function sampleRows(): ImportRow[] {
  const review = [
    reviewRow(7, 'zero_price', 'price', { name: 'Yoga Mat', sku: 'YM-015', price: 'free' }),
    reviewRow(25, 'empty_required_field', 'name', { name: '', sku: 'HD-099' }),
    reviewRow(41, 'empty_required_field', 'name', { name: '      ', sku: 'WS-001' }),
    reviewRow(47, 'zero_price', 'price', { name: 'Mystery Box', sku: 'MB-001', price: '0.00' }),
    reviewRow(50, 'empty_required_field', 'weight_kg', {
      name: 'Gaming Keyboard',
      sku: 'GK-088',
      weight_kg: '',
    }),
    reviewRow(52, 'empty_required_field', 'category', {
      name: 'Gift Card',
      sku: 'GC-025',
      category: '',
    }),
  ]
  const rejected = [
    importRow(16, 'rejected', {
      issues: [issue('stock', 'negative_value', 'error', 'The stock must be 0 or more.')],
    }),
    importRow(20, 'rejected', {
      values: { name: "<script>alert('xss')</script>" },
      issues: [issue('name', 'markup_in_name', 'error', 'The name cannot contain < or >.')],
    }),
  ]
  const superseded = [2, 11, 56].map((line) =>
    importRow(line, 'superseded', { superseded_by: line === 2 ? 36 : 89 }),
  )
  const blank = [62, 63].map((line) => importRow(line, 'blank', { sku: null, name: null, raw: '' }))
  const taken = new Set([...review, ...rejected, ...superseded, ...blank].map((row) => row.line))
  const created: ImportRow[] = []
  for (let line = 3; created.length < 84; line += 1) {
    if (!taken.has(line)) {
      const warnings =
        line === 4
          ? [
              issue(
                'price',
                'currency_symbol_stripped',
                'warning',
                'The $ was removed; stored 29.99.',
              ),
            ]
          : line === 36 || line === 89
            ? [issue('sku', 'duplicate_sku_in_file', 'warning', 'This SKU appears more than once.')]
            : []
      created.push(importRow(line, 'create', { issues: warnings }))
    }
  }
  return [...review, ...rejected, ...superseded, ...blank, ...created].sort(
    (first, second) => first.line - second.line,
  )
}

export function updateRow(line: number, sku: string) {
  return importRow(line, 'update', {
    sku,
    name: 'Running Shoes',
    needs_confirmation: true,
    actions: ['confirm', 'skip'],
    changes: { price: { before: '89.99', after: '94.99' } },
  })
}

function summaryOf(batch: ImportBatch): ImportSummary {
  const { items, ...summary } = batch
  void items
  return summary
}

function refresh(batch: ImportBatch): void {
  const counts = Object.fromEntries(OUTCOMES.map((outcome) => [outcome, 0])) as Record<
    RowOutcome,
    number
  >
  for (const row of batch.items) {
    counts[row.outcome] += 1
    row.pending =
      (row.outcome === 'needs_review' && row.decision !== 'skipped') ||
      (row.outcome === 'update' && row.needs_confirmation && row.decision === null)
  }
  batch.summary = counts
  batch.pending_lines = batch.items.filter((row) => row.pending).map((row) => row.line)
  batch.committable = batch.status === 'PENDING_REVIEW' && batch.pending_lines.length === 0
  batch.warnings =
    batch.file_warnings.length +
    batch.items.flatMap((row) => row.issues.filter((found) => found.severity === 'warning')).length
}

function resolveRow(row: ImportRow, body: Record<string, unknown>, actor: string | null) {
  const record = (before: Record<string, unknown>, after: Record<string, unknown>) =>
    row.history.push({
      action: body.action as ImportRow['actions'][number],
      actor: actor ?? '',
      at: '2026-11-21T10:05:00Z',
      before,
      after,
      original_issues: row.issues.map((found) => found.code),
    })
  if (body.action === 'skip') {
    record({ decision: 'none' }, { decision: 'skipped' })
    row.decision = 'skipped'
    return
  }
  if (body.action === 'confirm') {
    record({ outcome: row.outcome }, { outcome: row.outcome === 'update' ? 'update' : 'create' })
    if (row.outcome === 'update') {
      row.decision = 'confirmed'
      return
    }
    row.outcome = 'create'
    row.decision = null
    row.issues = []
    row.actions = ['correct', 'skip']
    return
  }
  const values = body.values as Record<string, string>
  record({ outcome: row.outcome }, { outcome: 'create' })
  row.values = { ...row.values, ...values }
  row.name = row.values.name
  row.sku = row.values.sku
  row.decision = null
  const zeroPrice = Number(row.values.price) === 0
  row.outcome = zeroPrice ? 'needs_review' : 'create'
  row.issues = zeroPrice
    ? [issue('price', 'zero_price', 'review', 'The price is 0. Confirm it as a free gift.')]
    : []
  row.actions = zeroPrice ? ['confirm', 'correct', 'skip'] : ['correct', 'skip']
}

export function fakeImports(rows: ImportRow[] = sampleRows()) {
  const batch: ImportBatch = {
    id: IMPORT_ID,
    file_name: 'products.csv',
    sha256: 'a'.repeat(64),
    size_bytes: 8930,
    status: 'PENDING_REVIEW',
    uploaded_by: 'Maria',
    uploaded_at: '2026-11-21T10:00:00Z',
    expires_at: '2026-11-22T10:00:00Z',
    finished_at: null,
    rows: rows.length,
    summary: {} as ImportBatch['summary'],
    pending_lines: [],
    committable: false,
    result: {},
    warnings: 0,
    file_warnings: [],
    items: rows,
  }
  refresh(batch)
  const uploads: Upload[] = []
  const resolutions: Resolution[] = []
  const commitProblems: Response[] = []
  const state = {
    batch,
    uploads,
    resolutions,
    failNextCommit: (response: Response) => commitProblems.push(response),
    changeRow: (line: number, change: Partial<ImportRow>) => {
      const row = batch.items.find((item) => item.line === line)
      Object.assign(row ?? {}, change)
      refresh(batch)
    },
  }

  server.use(
    http.post(`${API}/imports`, async ({ request }) => {
      const body = await request.text()
      const url = new URL(request.url)
      uploads.push({
        contentType: request.headers.get('Content-Type'),
        actor: request.headers.get('X-Actor-Name'),
        fileName: url.searchParams.get('file_name'),
        body,
      })
      if (!body.startsWith('name,sku')) {
        return validationProblem([
          {
            field: 'file',
            code: 'missing_columns',
            message: 'These columns are missing: description, category, price, stock, weight_kg.',
          },
        ])
      }
      return HttpResponse.json(batch, { status: 201 })
    }),
    http.get(`${API}/imports/:id`, ({ params }) =>
      params.id === IMPORT_ID
        ? HttpResponse.json(batch)
        : problem({ status: 404, slug: 'not-found', title: 'The resource was not found.' }),
    ),
    http.patch(`${API}/imports/:id/rows/:line`, async ({ request, params }) => {
      const body = (await request.json()) as Record<string, unknown>
      const line = Number(params.line)
      const actor = request.headers.get('X-Actor-Name')
      resolutions.push({ line, actor, body })
      const row = batch.items.find((item) => item.line === line)
      if (row === undefined) {
        return problem({ status: 404, slug: 'not-found', title: 'The resource was not found.' })
      }
      const values = (body.values ?? {}) as Record<string, string>
      if (body.action === 'correct' && Object.values(values).some((value) => value === 'abc')) {
        return validationProblem([
          {
            field: 'price',
            code: 'invalid_number',
            message: 'The price is not a number like 19.99.',
          },
        ])
      }
      resolveRow(row, body, actor)
      refresh(batch)
      return HttpResponse.json({ batch: summaryOf(batch), row })
    }),
    http.post(`${API}/imports/:id/commit`, () => {
      const forced = commitProblems.shift()
      if (forced !== undefined) {
        return forced
      }
      if (!batch.committable) {
        return problem({
          status: 409,
          slug: 'import-not-committable',
          title: 'Some rows still need a decision before the import.',
          detail: `Resolve or skip these lines first: ${batch.pending_lines.join(', ')}.`,
          extra: { pending_lines: batch.pending_lines },
        })
      }
      batch.status = 'COMMITTED'
      batch.result = {
        created: batch.items.filter((row) => row.outcome === 'create' && row.decision !== 'skipped')
          .length,
        updated: batch.items.filter(
          (row) => row.outcome === 'update' && row.decision === 'confirmed',
        ).length,
        skipped: batch.items.filter((row) => row.decision === 'skipped').length,
      }
      refresh(batch)
      return HttpResponse.json(batch)
    }),
    http.delete(`${API}/imports/:id`, () => {
      batch.status = 'DISCARDED'
      refresh(batch)
      return HttpResponse.json(batch)
    }),
  )
  return state
}
