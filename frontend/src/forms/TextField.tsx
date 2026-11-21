import { useId, type InputHTMLAttributes } from 'react'
import type { FieldError } from 'react-hook-form'

import styles from './Forms.module.css'

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string
  error?: FieldError
}

export function TextField({ label, error, ...input }: TextFieldProps) {
  const id = useId()
  const errorId = `${id}-error`
  return (
    <div className={styles.field}>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        {...input}
      />
      {error?.message ? (
        <p id={errorId} className={styles.fieldError}>
          {error.message}
        </p>
      ) : null}
    </div>
  )
}
