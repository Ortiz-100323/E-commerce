import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

import {
  ADMIN_EMAIL,
  ADMIN_PASSWORD,
  APPROVED,
  archiveAll,
  createProduct,
  logInAsAdmin,
  runId,
} from './support'

const run = runId()
const SKU = `E2E-${run}-ACC`
const NAME = `E2E Notebook ${run}`
const NEW_PASSWORD = 'a long e2e password'

let api: APIRequestContext

test.beforeAll(async ({ playwright }, testInfo) => {
  api = await playwright.request.newContext({ baseURL: testInfo.project.use.baseURL })
  await createProduct(api, SKU, NAME, '6.00', 20)
})

test.afterAll(async () => {
  await archiveAll(api, [SKU])
  await api.dispose()
})

function shot(page: Page, name: string, project: string, fullPage = false) {
  return page.screenshot({ path: `results/evidence/${project}-${name}.png`, fullPage })
}

async function logInThroughTheForm(page: Page, email: string, password: string) {
  const form = page.getByRole('region', { name: 'I have an account' })
  await form.getByLabel('Email').fill(email)
  await form.getByLabel('Password').fill(password)
  await form.getByRole('button', { name: 'Log in' }).click()
}

test('one Log in button takes the admin to the admin area', async ({ page }, testInfo) => {
  await page.goto('/')
  await expect(page.getByRole('banner').getByRole('link', { name: 'Admin' })).toHaveCount(0)

  await page.getByRole('banner').getByRole('link', { name: 'Log in' }).click()
  await expect(page).toHaveURL(/\/login\?next=%2F$/)
  await shot(page, 'login-page', testInfo.project.name, true)
  await logInThroughTheForm(page, ADMIN_EMAIL, 'not the right password')
  await expect(page.getByRole('alert')).toHaveText('The email or password is incorrect.')
  await logInThroughTheForm(page, ADMIN_EMAIL, ADMIN_PASSWORD)

  await expect(page).toHaveURL(/\/admin\/products$/)
  await expect(page.getByRole('banner').getByRole('link', { name: 'Admin' })).toBeVisible()
  await expect(page.getByRole('banner').getByRole('button', { name: 'Log out' })).toBeVisible()
  await shot(page, 'admin-after-login', testInfo.project.name)

  await page.getByRole('banner').getByRole('button', { name: 'Log out' }).click()
  await expect(page.getByRole('banner').getByRole('link', { name: 'Log in' })).toBeVisible()
  await page.goto('/admin/products')
  await expect(page).toHaveURL(/\/login\?next=%2Fadmin%2Fproducts$/)
})

test('an admin creates another admin, who can log in', async ({ page, browser }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'One new admin per run is enough.')
  const email = `e2e-admin-${run.toLowerCase()}@example.com`
  await logInAsAdmin(page)
  await page.goto('/admin/accounts')

  const form = page.getByRole('region', { name: 'Create admin' })
  await form.getByLabel('Name').fill(`E2E Admin ${run}`)
  await form.getByLabel('Email').fill(email)
  await form.getByLabel('Password').fill(NEW_PASSWORD)
  await form.getByRole('button', { name: 'Create admin' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'can now log in' })).toBeVisible()
  await expect(page.getByRole('table', { name: 'Administrators' })).toContainText(email)
  await shot(page, 'admins-page', testInfo.project.name)

  const other = await browser.newContext({ baseURL: testInfo.project.use.baseURL })
  const second = await other.newPage()
  await second.goto('/login')
  await logInThroughTheForm(second, email, NEW_PASSWORD)
  await expect(second).toHaveURL(/\/admin\/products$/)
  await other.close()
})

test('a customer signs up, buys, finds the order in My orders and is kept out of the admin area', async ({
  page,
}, testInfo) => {
  const email = `e2e-buyer-${run.toLowerCase()}-${testInfo.project.name}@example.com`
  await page.goto(`/?q=${SKU}`)
  await page.getByRole('banner').getByRole('link', { name: 'Log in' }).click()

  const signUp = page.getByRole('region', { name: 'New here? Create an account' })
  await signUp.getByLabel('Name').fill('E2E Buyer')
  await signUp.getByLabel('Email').fill(email)
  await signUp.getByLabel('Password').fill(NEW_PASSWORD)
  await signUp.getByRole('button', { name: 'Create account' }).click()

  await expect(page).toHaveURL(new RegExp(`/\\?q=${SKU}$`))
  await expect(page.getByRole('banner').getByRole('link', { name: 'My orders' })).toBeVisible()
  await page.getByRole('button', { name: 'Add to cart' }).click()
  await page.getByRole('link', { name: 'Cart: 1 item' }).click()
  await page.getByRole('button', { name: 'Go to checkout' }).click()
  await expect(page.getByLabel('Name')).toHaveValue('E2E Buyer')
  await expect(page.getByLabel('Email')).toHaveValue(email)
  await expect(page.getByText('This order will be kept in My orders.')).toBeVisible()
  await page.getByLabel('Card number').fill(APPROVED)
  await page.getByLabel('Expiry (MM/YY)').fill('12/30')
  await page.getByLabel('CVC').fill('123')
  await page.getByRole('button', { name: 'Pay $6.00' }).click()

  await expect(page.getByRole('heading', { name: 'Thank you, E2E Buyer' })).toBeVisible()
  await page.getByRole('link', { name: 'See My orders' }).click()
  const orders = page.getByRole('list', { name: 'Orders' })
  await expect(orders.getByRole('listitem')).toHaveCount(1)
  await expect(orders).toContainText(NAME)
  await shot(page, 'my-orders', testInfo.project.name, true)

  await page.goto('/admin/products')
  await expect(page.getByRole('heading', { name: 'This area is for administrators' })).toBeVisible()
  await expect(page.getByRole('banner').getByRole('link', { name: 'Admin' })).toHaveCount(0)
  await shot(page, 'buyer-blocked', testInfo.project.name)

  const adminCall = await page.context().request.post('/api/v1/products', { data: {} })
  expect(adminCall.status()).toBe(403)

  await page.context().clearCookies()
  await logInAsAdmin(page)
  await page.goto(`/admin/orders?q=${encodeURIComponent(email)}`)
  const table = page.getByRole('table', { name: 'Orders' })
  const rows = table.getByRole('row', { name: /^Order [0-9A-F]{8}$/ })
  await expect(rows).toHaveCount(1)
  await expect(table).toContainText('Customer account')
  await shot(page, 'admin-orders', testInfo.project.name)
  await rows.first().getByText('E2E Buyer').click()
  await expect(page.getByRole('heading', { name: /^Order [0-9A-F]{8}$/ })).toBeVisible()
  await expect(page.getByText(NAME).first()).toBeVisible()
  await shot(page, 'admin-order-detail', testInfo.project.name, true)

  await page.goto(`/?q=${SKU}`)
  await expect(page.getByRole('listitem', { name: NAME })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Add to cart' })).toHaveCount(0)
  await expect(page.getByRole('banner').getByRole('link', { name: /^Cart: / })).toHaveCount(0)
  await page.goto('/checkout')
  await expect(
    page.getByRole('heading', { name: "Administrator accounts can't place orders" }),
  ).toBeVisible()
  await shot(page, 'admin-cannot-buy', testInfo.project.name)
})
