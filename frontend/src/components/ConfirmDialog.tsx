import { useId } from 'react'

import styles from './ConfirmDialog.module.css'

type ConfirmDialogProps = {
  title: string
  message?: string
  confirmLabel: string
  cancelLabel: string
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel,
  cancelLabel,
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const titleId = useId()
  return (
    <div className={styles.backdrop}>
      <div role="alertdialog" aria-modal="true" aria-labelledby={titleId} className={styles.dialog}>
        <h2 id={titleId}>{title}</h2>
        {message ? <p>{message}</p> : null}
        <div className={styles.actions}>
          <button type="button" onClick={onCancel} autoFocus>
            {cancelLabel}
          </button>
          <button type="button" className={styles.primary} onClick={onConfirm} disabled={busy}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
