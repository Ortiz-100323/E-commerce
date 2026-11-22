import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { sessionApi, type Account, type NewAccount } from '../../../api/session'
import type { MutationMeta } from '../../../app/queryClient'
import { NewAccountForm } from '../../account/NewAccountForm'
import styles from '../products/Products.module.css'

const adminsKey = ['admins'] as const

export function AdminsPage() {
  const client = useQueryClient()
  const admins = useQuery({ queryKey: adminsKey, queryFn: () => sessionApi.admins() })
  const meta: MutationMeta = { handledProblems: ['email-already-registered'] }
  const create = useMutation({
    mutationFn: (account: NewAccount) => sessionApi.createAdmin(account),
    onSuccess: () => client.invalidateQueries({ queryKey: adminsKey }),
    meta,
  })
  const [created, setCreated] = useState<Account | null>(null)

  return (
    <section aria-labelledby="admins-title">
      <div className={styles.toolbar}>
        <h2 id="admins-title">Admins</h2>
      </div>
      <p className={styles.lead}>
        Administrators manage products and imports. Customers create their own accounts when they
        sign up; an administrator can only be created here.
      </p>
      {admins.isPending ? <p>Loading the administrators…</p> : null}
      {admins.data ? (
        <div className={styles.tableWrap}>
          <table className={styles.table} aria-label="Administrators">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Email</th>
              </tr>
            </thead>
            <tbody>
              {admins.data.items.map((admin) => (
                <tr key={admin.id}>
                  <td>{admin.name}</td>
                  <td>{admin.email}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <section aria-labelledby="new-admin-title" className={styles.form}>
        <h3 id="new-admin-title" className={styles.formTitle}>
          Create admin
        </h3>
        {created ? (
          <p role="status" className={styles.created}>
            {created.name} can now log in as an administrator with {created.email}.
          </p>
        ) : null}
        <NewAccountForm
          submitLabel="Create admin"
          busyLabel="Creating…"
          pending={create.isPending}
          create={(account) => create.mutateAsync(account)}
          onCreated={setCreated}
          emailTakenMessage="An account with this email already exists. Each email can have only one account."
        />
      </section>
    </section>
  )
}
