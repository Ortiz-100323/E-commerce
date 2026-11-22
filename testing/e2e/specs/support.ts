import { expect, type APIRequestContext, type Page } from '@playwright/test'

export const API = '/api/v1'
export const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'admin@example.com'
export const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'local-admin-password-change-me'
export const APPROVED = '4242 4242 4242 4242'
export const DECLINED = '4000 0000 0000 0002'

type Product = { id: string; sku: string; stock: number; version: number }

export function runId(): string {
  const random = Math.floor(Math.random() * 1296).toString(36)
  return `${Date.now().toString(36)}${random}`.toUpperCase()
}

export async function createProduct(
  request: APIRequestContext,
  sku: string,
  name: string,
  price: string,
  stock: number,
  extra: Record<string, string | null> = {},
): Promise<Product> {
  await logInApi(request)
  const response = await request.post(`${API}/products`, {
    data: {
      sku,
      name,
      description: 'Created by the browser tests.',
      category: 'E2E tests',
      price,
      stock,
      weight_kg: '0.5',
      gift: Number(price) === 0,
      ...extra,
    },
  })
  expect(response.status(), await response.text()).toBe(201)
  return (await response.json()) as Product
}

export async function productBySku(request: APIRequestContext, sku: string): Promise<Product> {
  await logInApi(request)
  const response = await request.get(`${API}/products`, { params: { q: sku, status: 'ALL' } })
  expect(response.ok()).toBe(true)
  const body = (await response.json()) as { items: Product[] }
  const found = body.items.find((item) => item.sku === sku)
  expect(found, `product ${sku}`).toBeDefined()
  return found as Product
}

export async function archiveAll(request: APIRequestContext, skus: string[]): Promise<void> {
  await logInApi(request)
  for (const sku of skus) {
    const response = await request.get(`${API}/products`, { params: { q: sku, status: 'ALL' } })
    const body = (await response.json()) as { items: Product[] }
    for (const item of body.items.filter((product) => product.sku === sku)) {
      await request.delete(`${API}/products/${item.id}`)
    }
  }
}

const loggedIn = new WeakSet<APIRequestContext>()

export async function logInApi(request: APIRequestContext): Promise<void> {
  if (loggedIn.has(request)) {
    return
  }
  const response = await request.post(`${API}/session`, {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  })
  expect(response.status(), await response.text()).toBe(200)
  loggedIn.add(request)
}

export async function logInAsAdmin(page: Page): Promise<void> {
  const response = await page.context().request.post(`${API}/session`, {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  })
  expect(response.status(), await response.text()).toBe(200)
}

export async function checkOut(page: Page, card: string): Promise<void> {
  await page.getByRole('button', { name: 'Go to checkout' }).click()
  await page.getByLabel('Name').fill('E2E test')
  await page.getByLabel('Email').fill('e2e@example.com')
  await page.getByLabel('Card number').fill(card)
  await page.getByLabel('Expiry (MM/YY)').fill('12/30')
  await page.getByLabel('CVC').fill('123')
}
