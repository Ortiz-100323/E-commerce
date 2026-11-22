import { request } from './client'

export type Role = 'ADMIN' | 'BUYER'

export type Account = {
  id: string
  name: string
  email: string
  role: Role
}

export type Credentials = { email: string; password: string }

export type NewAccount = { name: string; email: string; password: string }

export const sessionApi = {
  current: () => request<Account>('GET', '/session'),
  logIn: (credentials: Credentials) => request<Account>('POST', '/session', { body: credentials }),
  logOut: () => request<void>('DELETE', '/session'),
  signUp: (account: NewAccount) => request<Account>('POST', '/accounts', { body: account }),
  admins: () => request<{ items: Account[] }>('GET', '/admin/accounts'),
  createAdmin: (account: NewAccount) =>
    request<Account>('POST', '/admin/accounts', { body: account }),
}
