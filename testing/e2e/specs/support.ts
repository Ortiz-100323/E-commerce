import { expect, type APIRequestContext, type Page } from '@playwright/test'

export const API = '/api/v1'
export const ACTOR = { 'X-Actor-Name': 'E2E test' }
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
  const response = await request.post(`${API}/products`, {
    headers: ACTOR,
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
  const response = await request.get(`${API}/products`, { params: { q: sku, status: 'ALL' } })
  expect(response.ok()).toBe(true)
  const body = (await response.json()) as { items: Product[] }
  const found = body.items.find((item) => item.sku === sku)
  expect(found, `product ${sku}`).toBeDefined()
  return found as Product
}

export async function archiveAll(request: APIRequestContext, skus: string[]): Promise<void> {
  for (const sku of skus) {
    const response = await request.get(`${API}/products`, { params: { q: sku, status: 'ALL' } })
    const body = (await response.json()) as { items: Product[] }
    for (const item of body.items.filter((product) => product.sku === sku)) {
      await request.delete(`${API}/products/${item.id}`, { headers: ACTOR })
    }
  }
}

export async function answerReviewerPrompt(page: Page): Promise<void> {
  const prompt = page.getByRole('dialog', { name: 'Who is reviewing?' })
  await prompt.getByLabel('Your name').fill('E2E test')
  await prompt.getByRole('button', { name: 'Continue' }).click()
  await expect(prompt).toBeHidden()
}

export async function checkOut(page: Page, card: string): Promise<void> {
  await page.getByRole('button', { name: 'Go to checkout' }).click()
  await page.getByLabel('Name').fill('E2E test')
  await page.getByLabel('Email').fill('e2e@example.com')
  await page.getByLabel('Card number').fill(card)
  await page.getByLabel('Expiry (MM/YY)').fill('12/30')
  await page.getByLabel('CVC').fill('123')
}
