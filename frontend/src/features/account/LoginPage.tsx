import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useNavigate, useSearchParams } from 'react-router'

import { ApiError } from '../../api/apiError'
import type { Account } from '../../api/session'
import { TextField } from '../../forms/TextField'
import { landingFor, sessionEndedKey, useLogIn, useSession, useSignUp } from '../../session/session'
import controls from '../../styles/controls.module.css'
import { logInSchema, type LogInValues } from './accountSchemas'
import styles from './Account.module.css'
import { NewAccountForm } from './NewAccountForm'

function retryText(error: ApiError): string {
  const seconds = Number(error.body.retry_after_seconds)
  const minutes = Number.isFinite(seconds) ? Math.max(1, Math.ceil(seconds / 60)) : 15
  return `Too many attempts. Try again in ${minutes} minute${minutes === 1 ? '' : 's'}.`
}

function LogInForm({ onLoggedIn }: { onLoggedIn: (account: Account) => void }) {
  const logIn = useLogIn()
  const [message, setMessage] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LogInValues>({
    resolver: zodResolver(logInSchema),
    defaultValues: { email: '', password: '' },
  })

  const submit = handleSubmit((values) => {
    if (logIn.isPending) {
      return
    }
    setMessage(null)
    logIn.mutate(
      { email: values.email.trim(), password: values.password },
      {
        onSuccess: onLoggedIn,
        onError: (error) => {
          if (error instanceof ApiError && error.problem === 'too-many-login-attempts') {
            setMessage(retryText(error))
          } else if (error instanceof ApiError && error.problem === 'invalid-credentials') {
            setMessage('The email or password is incorrect.')
          }
        },
      },
    )
  })

  return (
    <form noValidate onSubmit={(event) => void submit(event)} className={styles.form}>
      {message ? (
        <p role="alert" className={controls.alert}>
          {message}
        </p>
      ) : null}
      <TextField
        label="Email"
        type="email"
        autoComplete="username"
        error={errors.email}
        {...register('email')}
      />
      <TextField
        label="Password"
        type="password"
        autoComplete="current-password"
        error={errors.password}
        {...register('password')}
      />
      <button type="submit" className={controls.primary} disabled={logIn.isPending}>
        {logIn.isPending ? 'Logging in…' : 'Log in'}
      </button>
    </form>
  )
}

export function LoginPage() {
  const session = useSession()
  const signUp = useSignUp()
  const client = useQueryClient()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = params.get('next')
  const [ended] = useState(() => client.getQueryData<boolean>(sessionEndedKey) === true)

  const go = (account: Account) => void navigate(landingFor(account, next), { replace: true })

  if (session.data) {
    return <Navigate to={landingFor(session.data, next)} replace />
  }

  return (
    <section aria-labelledby="login-title" className={styles.page}>
      <h1 id="login-title">Log in</h1>
      {ended ? (
        <p role="status" className={controls.notice}>
          Your session ended. Log in again.
        </p>
      ) : null}
      <div className={styles.panels}>
        <section aria-labelledby="login-form-title" className={styles.panel}>
          <h2 id="login-form-title" className={styles.panelTitle}>
            I have an account
          </h2>
          <LogInForm onLoggedIn={go} />
        </section>
        <section aria-labelledby="signup-title" className={styles.panel}>
          <h2 id="signup-title" className={styles.panelTitle}>
            New here? Create an account
          </h2>
          <p className={styles.panelText}>
            Keep your orders in one place. You can still buy without an account.
          </p>
          <NewAccountForm
            submitLabel="Create account"
            busyLabel="Creating your account…"
            pending={signUp.isPending}
            create={(account) => signUp.mutateAsync(account)}
            onCreated={go}
          />
        </section>
      </div>
    </section>
  )
}
