import { useState, type FormEvent } from 'react'

import { ApiError, type FieldProblem } from '../../../api/apiError'
import type { ImportBatch, ImportRow, Resolve } from '../../../api/imports'
import { FormProblems } from '../../../forms/FormProblems'
import { COLUMNS, columnLabel, confirmLabel, lineList, reviewCodes, warningsOf } from './importText'
import styles from './Imports.module.css'
import { useResolveRow } from './queries'

type RowProps = { batchId: string; row: ImportRow; locked: boolean }

function problemsOf(error: unknown): FieldProblem[] {
  if (!(error instanceof ApiError)) {
    return []
  }
  if (error.isValidation) {
    return error.errors.map((problem) => ({ ...problem, field: columnLabel(problem.field) }))
  }
  return [
    {
      location: 'body',
      field: '',
      code: error.problem,
      message: error.detail ?? error.title,
      params: {},
    },
  ]
}

function RawLine({ row }: { row: ImportRow }) {
  return (
    <p>
      CSV line {row.line}: <code className={styles.raw}>{row.raw || '(empty line)'}</code>
    </p>
  )
}

function changedValues(row: ImportRow, values: Record<string, string>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(values).filter(([key, value]) => value !== (row.values[key] ?? '')),
  )
}

export function ReviewRowCard({ batchId, row, locked }: RowProps) {
  const resolve = useResolveRow(batchId)
  const [values, setValues] = useState<Record<string, string>>(() => ({ ...row.values }))
  const changed = changedValues(row, values)
  const busy = locked || resolve.isPending
  const send = (action: Resolve) => resolve.mutate({ line: row.line, resolve: action })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    send({ action: 'correct', values: changed })
  }

  return (
    <article aria-label={`Line ${row.line}`} className={styles.card}>
      <h3>
        Line {row.line} · {row.sku ?? 'no SKU'} · {row.name ?? 'no name'}
        {row.decision === 'skipped' ? <span className={styles.skipped}> · Skipped</span> : null}
      </h3>
      <ul className={styles.issues}>
        {row.issues.map((issue) => (
          <li key={`${issue.field}:${issue.code}`}>
            {columnLabel(issue.field)}: {issue.message}
          </li>
        ))}
      </ul>
      <RawLine row={row} />
      <form onSubmit={submit} aria-label={`Correct line ${row.line}`}>
        <div className={styles.editor}>
          {COLUMNS.map((column) => (
            <label key={column.key}>
              {column.label}
              <input
                value={values[column.key] ?? ''}
                disabled={busy}
                onChange={(event) =>
                  setValues((current) => ({ ...current, [column.key]: event.target.value }))
                }
              />
            </label>
          ))}
        </div>
        <FormProblems problems={problemsOf(resolve.error)} />
        <div className={styles.rowActions}>
          <button
            type="submit"
            className={styles.primary}
            disabled={busy || Object.keys(changed).length === 0}
          >
            Save correction
          </button>
          {row.actions.includes('confirm') && reviewCodes(row).length > 0 ? (
            <button
              type="button"
              className={styles.secondary}
              disabled={busy}
              onClick={() => send({ action: 'confirm', expected_outcome: row.outcome })}
            >
              {confirmLabel(row)}
            </button>
          ) : null}
          {row.decision !== 'skipped' ? (
            <button
              type="button"
              className={styles.secondary}
              disabled={busy}
              onClick={() => send({ action: 'skip' })}
            >
              Skip this row
            </button>
          ) : null}
        </div>
      </form>
    </article>
  )
}

export function UpdateRowCard({ batchId, row, locked }: RowProps) {
  const resolve = useResolveRow(batchId)
  const busy = locked || resolve.isPending || !row.needs_confirmation
  return (
    <article aria-label={`Line ${row.line}`} className={styles.card}>
      <h3>
        Line {row.line} · {row.sku} · {row.name}
      </h3>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">Field</th>
            <th scope="col">Now</th>
            <th scope="col">After the import</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(row.changes).map(([field, change]) => (
            <tr key={field}>
              <th scope="row">{columnLabel(field)}</th>
              <td className={styles.before}>{change.before || '(empty)'}</td>
              <td className={styles.after}>{change.after || '(empty)'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {warningsOf(row).map((issue) => (
        <p key={issue.code}>{issue.message}</p>
      ))}
      <FormProblems problems={problemsOf(resolve.error)} />
      <label>
        <input
          type="checkbox"
          checked={row.decision === 'confirmed' || !row.needs_confirmation}
          disabled={busy}
          onChange={(event) =>
            resolve.mutate({
              line: row.line,
              resolve: event.target.checked
                ? { action: 'confirm', expected_outcome: row.outcome }
                : { action: 'skip' },
            })
          }
        />{' '}
        Confirm this update
        {row.decision === 'skipped' ? <span className={styles.skipped}> · Skipped</span> : null}
      </label>
    </article>
  )
}

export function OutcomeTable({ rows }: { rows: ImportRow[] }) {
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th scope="col">Line</th>
          <th scope="col">SKU</th>
          <th scope="col">Name</th>
          <th scope="col">Category</th>
          <th scope="col">Price</th>
          <th scope="col">Stock</th>
          <th scope="col">Weight (kg)</th>
          <th scope="col">Notes</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.line} aria-label={`Line ${row.line}`}>
            <td>{row.line}</td>
            <td>{row.sku}</td>
            <td>{row.name}</td>
            <td>{row.values.category}</td>
            <td>{row.values.price}</td>
            <td>{row.values.stock}</td>
            <td>{row.values.weight_kg}</td>
            <td>
              {row.history.length > 0 ? <span className={styles.badge}>Reviewed</span> : null}
              {row.decision === 'skipped' ? <span className={styles.skipped}> Skipped</span> : null}
              {warningsOf(row).map((issue) => (
                <span key={issue.code}> {issue.message}</span>
              ))}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function RejectedTable({ rows }: { rows: ImportRow[] }) {
  return (
    <>
      <p>Rejected rows can't be edited here. Fix them in the source file and upload it again.</p>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">Line</th>
            <th scope="col">SKU</th>
            <th scope="col">Why</th>
            <th scope="col">Raw line</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.line} aria-label={`Line ${row.line}`}>
              <td>{row.line}</td>
              <td>{row.sku}</td>
              <td>
                <ul className={styles.issues}>
                  {row.issues
                    .filter((issue) => issue.severity === 'error')
                    .map((issue) => (
                      <li key={`${issue.field}:${issue.code}`}>
                        {columnLabel(issue.field)}: {issue.message}
                      </li>
                    ))}
                </ul>
              </td>
              <td>
                <code className={styles.raw}>{row.raw}</code>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}

export function SupersededTable({ rows }: { rows: ImportRow[] }) {
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th scope="col">Line</th>
          <th scope="col">SKU</th>
          <th scope="col">Replaced by</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.line} aria-label={`Line ${row.line}`}>
            <td>{row.line}</td>
            <td>{row.sku}</td>
            <td>Line {row.superseded_by}, later in the file</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function BlankList({ rows }: { rows: ImportRow[] }) {
  return <p>Empty lines, ignored: {lineList(rows.map((row) => row.line))}.</p>
}

export function WarningsTable({ batch }: { batch: ImportBatch }) {
  const rows = batch.items.flatMap((row) =>
    warningsOf(row).map((issue) => ({ line: String(row.line), issue })),
  )
  const all = [...batch.file_warnings.map((issue) => ({ line: 'File', issue })), ...rows]
  if (all.length === 0) {
    return <p>No warnings.</p>
  }
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th scope="col">Line</th>
          <th scope="col">Field</th>
          <th scope="col">Warning</th>
        </tr>
      </thead>
      <tbody>
        {all.map(({ line, issue }) => (
          <tr key={`${line}:${issue.field}:${issue.code}`}>
            <td>{line}</td>
            <td>{columnLabel(issue.field)}</td>
            <td>{issue.message}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
