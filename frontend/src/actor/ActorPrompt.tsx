import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import type { z } from 'zod'

import { TextField } from '../forms/TextField'
import { actorFormSchema, MAX_ACTOR_LENGTH } from './actorName'
import styles from './ActorPrompt.module.css'

type ActorFormInput = z.input<typeof actorFormSchema>
type ActorFormOutput = z.output<typeof actorFormSchema>

type ActorPromptProps = {
  initialName?: string
  onSave: (name: string) => void
  onCancel?: () => void
}

export function ActorPrompt({ initialName = '', onSave, onCancel }: ActorPromptProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ActorFormInput, unknown, ActorFormOutput>({
    resolver: zodResolver(actorFormSchema),
    defaultValues: { name: initialName },
  })

  return (
    <div className={styles.backdrop}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="actor-prompt-title"
        className={styles.dialog}
      >
        <h2 id="actor-prompt-title">Who is reviewing?</h2>
        <p className={styles.note}>
          Your name is saved with every change you make, so the history shows who did what.
        </p>
        <form onSubmit={handleSubmit((values) => onSave(values.name))} noValidate>
          <TextField
            label="Your name"
            autoFocus
            autoComplete="name"
            maxLength={MAX_ACTOR_LENGTH * 2}
            error={errors.name}
            {...register('name')}
          />
          <div className={styles.actions}>
            {onCancel ? (
              <button type="button" onClick={onCancel}>
                Cancel
              </button>
            ) : null}
            <button type="submit">Continue</button>
          </div>
        </form>
      </div>
    </div>
  )
}
