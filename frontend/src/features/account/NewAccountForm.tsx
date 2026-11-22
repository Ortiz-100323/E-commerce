import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { ApiError, type FieldProblem } from '../../api/apiError'
import type { Account, NewAccount } from '../../api/session'
import { applyProblemToForm } from '../../forms/applyProblemToForm'
import { FormProblems } from '../../forms/FormProblems'
import { TextField } from '../../forms/TextField'
import controls from '../../styles/controls.module.css'
import {
  MIN_PASSWORD_LENGTH,
  NEW_ACCOUNT_FIELDS,
  newAccountSchema,
  type NewAccountValues,
} from './accountSchemas'
import styles from './Account.module.css'

type NewAccountFormProps = {
  submitLabel: string
  busyLabel: string
  pending: boolean
  create: (account: NewAccount) => Promise<Account>
  onCreated: (account: Account) => void
  emailTakenMessage?: string
}

const EMPTY: NewAccountValues = { name: '', email: '', password: '' }

export function NewAccountForm({
  submitLabel,
  busyLabel,
  pending,
  create,
  onCreated,
  emailTakenMessage = 'An account with this email already exists. Log in instead.',
}: NewAccountFormProps) {
  const [problems, setProblems] = useState<FieldProblem[]>([])
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors },
  } = useForm<NewAccountValues>({ resolver: zodResolver(newAccountSchema), defaultValues: EMPTY })

  const submit = handleSubmit(async (values) => {
    if (pending) {
      return
    }
    setProblems([])
    try {
      const account = await create({
        name: values.name.trim(),
        email: values.email.trim(),
        password: values.password,
      })
      reset(EMPTY)
      onCreated(account)
    } catch (error) {
      if (error instanceof ApiError && error.problem === 'email-already-registered') {
        setError(
          'email',
          { type: error.problem, message: emailTakenMessage },
          { shouldFocus: true },
        )
        return
      }
      setProblems(applyProblemToForm(error, NEW_ACCOUNT_FIELDS, setError))
    }
  })

  return (
    <form noValidate onSubmit={(event) => void submit(event)} className={styles.form}>
      <FormProblems problems={problems} />
      <TextField label="Name" autoComplete="name" error={errors.name} {...register('name')} />
      <TextField
        label="Email"
        type="email"
        autoComplete="email"
        error={errors.email}
        {...register('email')}
      />
      <TextField
        label="Password"
        type="password"
        autoComplete="new-password"
        hint={`At least ${MIN_PASSWORD_LENGTH} characters. A short sentence works well.`}
        error={errors.password}
        {...register('password')}
      />
      <button type="submit" className={controls.primary} disabled={pending}>
        {pending ? busyLabel : submitLabel}
      </button>
    </form>
  )
}
