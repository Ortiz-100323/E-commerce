import { useId, type TextareaHTMLAttributes } from 'react'
import type { FieldError } from 'react-hook-form'

import styles from './Forms.module.css'

type TextAreaFieldProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string
  error?: FieldError
}

export function TextAreaField({ label, error, ...textarea }: TextAreaFieldProps) {
  const id = useId()
  const errorId = `${id}-error`
  return (
    <div className={styles.field}>
      <label htmlFor={id}>{label}</label>
      <textarea
        id={id}
        rows={4}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        {...textarea}
      />
      {error?.message ? (
        <p id={errorId} className={styles.fieldError}>
          {error.message}
        </p>
      ) : null}
    </div>
  )
}
