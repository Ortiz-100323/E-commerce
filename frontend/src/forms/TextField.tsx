import { useId, type InputHTMLAttributes } from 'react'
import type { FieldError } from 'react-hook-form'

import styles from './Forms.module.css'

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string
  hint?: string
  error?: FieldError
}

export function TextField({ label, hint, error, ...input }: TextFieldProps) {
  const id = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const describedBy = [hint ? hintId : null, error?.message ? errorId : null]
    .filter((value) => value !== null)
    .join(' ')
  return (
    <div className={styles.field}>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        {...input}
      />
      {hint ? (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      ) : null}
      {error?.message ? (
        <p id={errorId} className={styles.fieldError}>
          {error.message}
        </p>
      ) : null}
    </div>
  )
}
