import { http, HttpResponse } from 'msw/http'

import type { Order } from '../../../frontend/src/api/orders'
import type { Account, Role } from '../../../frontend/src/api/session'
import { API, problem } from './api'

type StoredAccount = Account & { password: string }

export const TEST_PASSWORD = 'correct horse battery'

const SEEDED: StoredAccount[] = [
  {
    id: 'acc-admin-maria',
    name: 'Maria',
    email: 'maria@example.com',
    role: 'ADMIN',
    password: TEST_PASSWORD,
  },
  {
    id: 'acc-buyer-bea',
    name: 'Bea',
    email: 'bea@example.com',
    role: 'BUYER',
    password: TEST_PASSWORD,
  },
]

const state: {
  accounts: StoredAccount[]
  current: Account | null
  failures: number
  requests: { method: string; path: string; body: unknown }[]
} = { accounts: [...SEEDED], current: null, failures: 0, requests: [] }

function publicView({ password: _password, ...account }: StoredAccount): Account {
  return account
}

export function resetFakeSession(): void {
  state.accounts = SEEDED.map((account) => ({ ...account }))
  state.current = null
  state.failures = 0
  state.requests = []
  myOrders.items = []
}

export function logInAs(role: Role, name = role === 'ADMIN' ? 'Maria' : 'Bea'): Account {
  const found = state.accounts.find((account) => account.role === role && account.name === name)
  const account =
    found ??
    (() => {
      const created: StoredAccount = {
        id: `acc-${name.toLowerCase()}`,
        name,
        email: `${name.toLowerCase()}@example.com`,
        role,
        password: TEST_PASSWORD,
      }
      state.accounts.push(created)
      return created
    })()
  state.current = publicView(account)
  return state.current
}

export function endFakeSession(): void {
  state.current = null
}

export function currentFakeAccount(): Account | null {
  return state.current
}

export function fakeSessionRequests() {
  return state.requests
}

export function fakeAccounts(): Account[] {
  return state.accounts.map(publicView)
}

function authenticationRequired() {
  return problem({ status: 401, slug: 'authentication-required', title: 'Log in to continue.' })
}

function adminRequired() {
  return problem({ status: 403, slug: 'admin-required', title: 'This is for administrators only.' })
}

export function requireAdmin(): Response | null {
  if (state.current === null) {
    return authenticationRequired()
  }
  return state.current.role === 'ADMIN' ? null : adminRequired()
}

export function requireBuyer(): Response | null {
  if (state.current === null) {
    return authenticationRequired()
  }
  return state.current.role === 'BUYER'
    ? null
    : problem({
        status: 403,
        slug: 'buyer-required',
        title: 'This is for customer accounts only.',
      })
}

function emailTaken() {
  return problem({
    status: 409,
    slug: 'email-already-registered',
    title: 'An account with this email already exists. Log in instead.',
  })
}

async function bodyOf(request: Request): Promise<Record<string, string>> {
  const body = (await request.json().catch(() => ({}))) as Record<string, string>
  state.requests.push({ method: request.method, path: new URL(request.url).pathname, body })
  return body
}

function create(body: Record<string, string>, role: Role): StoredAccount | null {
  const email = (body.email ?? '').trim().toLowerCase()
  if (state.accounts.some((account) => account.email === email)) {
    return null
  }
  const account: StoredAccount = {
    id: `acc-${state.accounts.length + 1}`,
    name: (body.name ?? '').trim(),
    email,
    role,
    password: body.password ?? '',
  }
  state.accounts.push(account)
  return account
}

export const sessionHandlers = [
  http.get(`${API}/session`, () =>
    state.current === null ? authenticationRequired() : HttpResponse.json(state.current),
  ),
  http.post(`${API}/session`, async ({ request }) => {
    const body = await bodyOf(request)
    if (state.failures >= 5) {
      return problem({
        status: 429,
        slug: 'too-many-login-attempts',
        title: 'Too many attempts. Wait a few minutes and try again.',
        extra: { retry_after_seconds: 600 },
      })
    }
    const email = (body.email ?? '').trim().toLowerCase()
    const found = state.accounts.find(
      (account) => account.email === email && account.password === body.password,
    )
    if (found === undefined) {
      state.failures += 1
      return problem({
        status: 401,
        slug: 'invalid-credentials',
        title: 'The email or password is incorrect.',
      })
    }
    state.failures = 0
    state.current = publicView(found)
    return HttpResponse.json(state.current)
  }),
  http.delete(`${API}/session`, () => {
    state.current = null
    return new HttpResponse(null, { status: 204 })
  }),
  http.post(`${API}/accounts`, async ({ request }) => {
    const body = await bodyOf(request)
    const created = create(body, 'BUYER')
    if (created === null) {
      return emailTaken()
    }
    state.current = publicView(created)
    return HttpResponse.json(state.current, { status: 201 })
  }),
  http.get(`${API}/admin/accounts`, () => {
    const refused = requireAdmin()
    if (refused) {
      return refused
    }
    const admins = state.accounts.filter((account) => account.role === 'ADMIN').map(publicView)
    return HttpResponse.json({ items: admins })
  }),
  http.post(`${API}/admin/accounts`, async ({ request }) => {
    const refused = requireAdmin()
    if (refused) {
      return refused
    }
    const created = create(await bodyOf(request), 'ADMIN')
    return created === null ? emailTaken() : HttpResponse.json(publicView(created), { status: 201 })
  }),
]

const myOrders: { items: Order[] } = { items: [] }

export function setMyOrders(orders: Order[]): void {
  myOrders.items = orders
}

export const myOrdersHandler = http.get(`${API}/me/orders`, ({ request }) => {
  const refused = requireBuyer()
  if (refused) {
    return refused
  }
  const page = Number(new URL(request.url).searchParams.get('page') ?? '1')
  const size = 10
  return HttpResponse.json({
    items: myOrders.items.slice((page - 1) * size, page * size),
    total: myOrders.items.length,
    page,
    page_size: size,
  })
})
