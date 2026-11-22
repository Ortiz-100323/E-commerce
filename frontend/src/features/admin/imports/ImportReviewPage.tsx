import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../../../api/apiError'
import type { ImportBatch, ImportRow } from '../../../api/imports'
import { ConfirmDialog } from '../../../components/ConfirmDialog'
import { formatDateTime } from '../products/format'
import {
  BlankList,
  OutcomeTable,
  RejectedTable,
  ReviewRowCard,
  SupersededTable,
  UpdateRowCard,
  WarningsTable,
} from './ImportRows'
import {
  firstTab,
  lineList,
  ROW_TABS,
  rowsInTab,
  statusLabel,
  type RowTab,
  type TabKey,
} from './importText'
import styles from './Imports.module.css'
import { useCommitImport, useDiscardImport, useImport, useResolveRow } from './queries'

function FinishProblem({ error }: { error: unknown }) {
  if (!(error instanceof ApiError)) {
    return null
  }
  const lines = error.body.lines ?? error.body.pending_lines
  return (
    <div role="alert" className={styles.alert}>
      <p>
        <strong>{error.title}</strong>
      </p>
      {error.detail ? <p>{error.detail}</p> : null}
      {error.problem === 'import-stale-rows' && Array.isArray(lines) ? (
        <p>
          Nothing was imported. The rows on lines {lineList(lines as number[])} now show the latest
          changes; confirm them again, then commit.
        </p>
      ) : null}
    </div>
  )
}

function StatusBanner({ batch }: { batch: ImportBatch }) {
  if (batch.status === 'COMMITTED') {
    return (
      <div role="status" className={styles.success}>
        <p>
          <strong>Imported.</strong> {batch.result.created ?? 0} created,{' '}
          {batch.result.updated ?? 0} updated, {batch.result.skipped ?? 0} skipped.
        </p>
        <p>
          <Link to="/admin/products">See the products</Link>
        </p>
      </div>
    )
  }
  if (batch.status === 'DISCARDED') {
    return (
      <div role="status" className={styles.info}>
        <p>This import was discarded. Nothing was imported.</p>
      </div>
    )
  }
  if (batch.status === 'EXPIRED') {
    return (
      <div role="status" className={styles.info}>
        <p>This import expired 24 hours after the upload. Upload the file again.</p>
      </div>
    )
  }
  return null
}

function ConfirmAllUpdates({ batch, locked }: { batch: ImportBatch; locked: boolean }) {
  const resolve = useResolveRow(batch.id)
  const waiting = batch.items.filter((row) => row.outcome === 'update' && row.pending)
  if (waiting.length === 0) {
    return null
  }
  const confirmAll = async () => {
    for (const row of waiting) {
      await resolve.mutateAsync({
        line: row.line,
        resolve: { action: 'confirm', expected_outcome: row.outcome },
      })
    }
  }
  return (
    <button
      type="button"
      className={styles.secondary}
      disabled={locked || resolve.isPending}
      onClick={() => void confirmAll().catch(() => undefined)}
    >
      Confirm all {waiting.length} updates
    </button>
  )
}

const reviewCardKey = (row: ImportRow) => `${row.line}-${row.history.length}-${row.outcome}`

type PanelProps = { rows: ImportRow[]; batch: ImportBatch; locked: boolean }

function SkippedPanel({ rows, batch, locked }: PanelProps) {
  const reviews = rows.filter((row) => row.outcome === 'needs_review')
  const updates = rows.filter((row) => row.outcome === 'update')
  const others = rows.filter((row) => row.outcome !== 'needs_review' && row.outcome !== 'update')
  return (
    <>
      <p>
        These rows will not be imported. Changed your mind? Correct or confirm a row, or tick an
        update again, and it goes back to its tab.
      </p>
      {reviews.map((row) => (
        <ReviewRowCard key={reviewCardKey(row)} batchId={batch.id} row={row} locked={locked} />
      ))}
      {updates.map((row) => (
        <UpdateRowCard key={row.line} batchId={batch.id} row={row} locked={locked} />
      ))}
      {others.length > 0 ? <OutcomeTable rows={others} /> : null}
    </>
  )
}

const EDITABLE_TABS = new Set<TabKey>(['needs_review', 'update', 'skipped'])

function nextLineAfter(rows: ImportRow[], index: number): number | undefined {
  return rows[index + 1]?.line ?? (index > 0 ? rows[0].line : undefined)
}

function TabPanel({ tab, batch, locked }: { tab: TabKey; batch: ImportBatch; locked: boolean }) {
  if (tab === 'warnings') {
    return <WarningsTable batch={batch} />
  }
  const rows = rowsInTab(batch.items, tab)
  if (rows.length === 0) {
    return <p>No rows here.</p>
  }
  if (batch.status !== 'PENDING_REVIEW' && EDITABLE_TABS.has(tab)) {
    return <OutcomeTable rows={rows} />
  }
  switch (tab) {
    case 'skipped':
      return <SkippedPanel rows={rows} batch={batch} locked={locked} />
    case 'needs_review':
      return rows.map((row, index) => (
        <ReviewRowCard
          key={reviewCardKey(row)}
          batchId={batch.id}
          row={row}
          locked={locked}
          nextLine={nextLineAfter(rows, index)}
        />
      ))
    case 'update':
      return (
        <>
          <ConfirmAllUpdates batch={batch} locked={locked} />
          {rows.map((row) => (
            <UpdateRowCard key={row.line} batchId={batch.id} row={row} locked={locked} />
          ))}
        </>
      )
    case 'rejected':
      return <RejectedTable rows={rows} />
    case 'superseded':
      return <SupersededTable rows={rows} />
    case 'blank':
      return <BlankList rows={rows} />
    default:
      return <OutcomeTable rows={rows} />
  }
}

function Review({ batch }: { batch: ImportBatch }) {
  const commit = useCommitImport(batch.id)
  const discard = useDiscardImport(batch.id)
  const [tab, setTab] = useState<TabKey>(() => firstTab(batch.items))
  const [discarding, setDiscarding] = useState(false)
  const pending = batch.status === 'PENDING_REVIEW'
  const locked = !pending || commit.isPending || discard.isPending
  const count = (key: RowTab) => rowsInTab(batch.items, key).length
  const tabs: { key: TabKey; label: string; count: number }[] = [
    ...ROW_TABS.map((item) => ({ ...item, count: count(item.key) })),
    { key: 'warnings', label: 'Warnings', count: batch.warnings },
  ]

  return (
    <section aria-labelledby="review-title">
      <div className={styles.header}>
        <div>
          <h2 id="review-title">Review import: {batch.file_name}</h2>
          <p className={styles.meta}>
            {statusLabel(batch.status)} · uploaded by {batch.uploaded_by} on{' '}
            {formatDateTime(batch.uploaded_at)} UTC · {batch.rows} rows
          </p>
        </div>
        <Link to="/admin/imports/new">Upload another file</Link>
      </div>
      <StatusBanner batch={batch} />
      <FinishProblem error={commit.error ?? discard.error} />
      {pending ? (
        <div className={styles.commitBar}>
          <button
            type="button"
            className={styles.primary}
            disabled={!batch.committable || locked}
            onClick={() => commit.mutate()}
          >
            {commit.isPending ? 'Importing…' : 'Commit import'}
          </button>
          <button
            type="button"
            className={styles.secondary}
            disabled={locked}
            onClick={() => setDiscarding(true)}
          >
            Discard import
          </button>
          <p className={styles.hint}>
            {batch.committable
              ? 'Every row has a decision. Commit applies everything at once, or nothing.'
              : `Waiting for a decision on lines ${lineList(batch.pending_lines)}.`}
          </p>
        </div>
      ) : null}
      <div role="tablist" aria-label="Rows by outcome" className={styles.tabs}>
        {tabs.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            id={`tab-${item.key}`}
            aria-selected={tab === item.key}
            aria-controls="import-panel"
            className={styles.tab}
            onClick={() => setTab(item.key)}
          >
            {item.label} ({item.count})
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id="import-panel"
        aria-labelledby={`tab-${tab}`}
        className={styles.panel}
      >
        <TabPanel tab={tab} batch={batch} locked={locked} />
      </div>
      {discarding ? (
        <ConfirmDialog
          title="Discard this import?"
          message="Nothing will be imported. The file and your decisions stay in the audit trail."
          confirmLabel="Discard import"
          cancelLabel="Keep reviewing"
          busy={discard.isPending}
          onConfirm={() => discard.mutate(undefined, { onSettled: () => setDiscarding(false) })}
          onCancel={() => setDiscarding(false)}
        />
      ) : null}
    </section>
  )
}

export function ImportReviewPage() {
  const { importId = '' } = useParams()
  const batch = useImport(importId)

  if (batch.isPending) {
    return <p>Loading…</p>
  }
  if (batch.isError) {
    const missing = batch.error instanceof ApiError && batch.error.problem === 'not-found'
    return (
      <div role="alert" className={styles.alert}>
        <p>{missing ? 'This import was not found.' : 'The import could not be loaded.'}</p>
        <p>
          <Link to="/admin/imports/new">Upload a file</Link>
        </p>
      </div>
    )
  }
  return <Review batch={batch.data} />
}
