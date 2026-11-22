import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

import { archiveAll, createProduct, runId } from './support'

const run = runId()
const sku = (key: string) => `E2E-${run}-${key}`
const TABLE = { key: 'TABLE', name: `E2E Table lamp ${run}` }
const CART = { key: 'CART', name: `E2E Cart mug ${run}` }

let api: APIRequestContext

test.beforeAll(async ({ playwright }, testInfo) => {
  api = await playwright.request.newContext({ baseURL: testInfo.project.use.baseURL })
  await createProduct(api, sku(TABLE.key), TABLE.name, '19.00', 8)
  await createProduct(api, sku(CART.key), CART.name, '7.50', 2)
})

test.afterAll(async () => {
  await archiveAll(api, [sku(TABLE.key), sku(CART.key), sku('NEW')])
  await api.dispose()
})

async function asReviewer(page: Page) {
  await page.addInitScript(() => window.localStorage.setItem('ecommerce.actor', 'E2E reviewer'))
}

function shot(page: Page, name: string, project: string, fullPage = false) {
  return page.screenshot({ path: `results/evidence/${project}-${name}.png`, fullPage })
}

test('a duplicate SKU names the product that has it, with links to it', async ({
  page,
}, testInfo) => {
  await asReviewer(page)
  await page.goto('/admin/products/new')
  await page.getByLabel('SKU').fill(sku(TABLE.key))
  await page.getByLabel('Name').fill(`E2E Copy ${run}`)
  await page.getByLabel('Description').fill('A copy that must be refused.')
  await page.getByLabel('Category').fill('E2E tests')
  await page.getByLabel('Price (USD)').fill('5.00')
  await page.getByLabel('Stock').fill('1')
  await page.getByLabel('Weight (kg)').fill('0.2')
  await page.getByRole('button', { name: 'Create product' }).click()

  await expect(
    page.getByText(`SKU ${sku(TABLE.key)} is already taken by ${TABLE.name}.`),
  ).toBeVisible()
  await expect(page.getByRole('link', { name: `Edit ${TABLE.name}` })).toBeVisible()
  await shot(page, 'duplicate-sku', testInfo.project.name)
  await page.getByRole('link', { name: `View ${TABLE.name}` }).click()
  await expect(page.getByRole('heading', { level: 1, name: TABLE.name })).toBeVisible()
})

test('the admin table keeps SKUs on one line and its actions in reach', async ({
  page,
}, testInfo) => {
  await asReviewer(page)
  await page.goto(`/admin/products?q=${sku(TABLE.key)}`)
  const row = page.getByRole('row', { name: sku(TABLE.key) })
  await expect(row).toBeVisible()
  const skuCell = row.getByRole('cell').first()
  expect(await skuCell.evaluate((cell) => getComputedStyle(cell).whiteSpace)).toBe('nowrap')
  const toggle = row.getByRole('button', { name: `Actions for ${sku(TABLE.key)}` })

  if (testInfo.project.name === 'desktop') {
    await expect(toggle).toBeHidden()
    await expect(row.getByRole('link', { name: 'Edit' })).toBeVisible()
    await expect(row.getByRole('button', { name: 'Archive' })).toBeVisible()
    return
  }
  await expect(row.getByRole('link', { name: 'Edit' })).toBeHidden()
  await toggle.click()
  const sheet = page.getByRole('group', { name: `Actions for ${sku(TABLE.key)}` })
  await expect(sheet.getByRole('link', { name: 'Edit' })).toBeVisible()
  const box = await sheet.boundingBox()
  const viewport = page.viewportSize()
  expect(Math.round((box?.y ?? 0) + (box?.height ?? 0))).toBe(viewport?.height)
  await shot(page, 'admin-actions-sheet', testInfo.project.name)
  await page.keyboard.press('Escape')
  await expect(sheet.getByRole('link', { name: 'Edit' })).toBeHidden()
})

test('a success message closes by itself and stays clear of the actions', async ({
  page,
}, testInfo) => {
  await asReviewer(page)
  await page.goto(`/admin/products?q=${sku(TABLE.key)}`)
  const row = page.getByRole('row', { name: sku(TABLE.key) })
  if (testInfo.project.name !== 'desktop') {
    await row.getByRole('button', { name: `Actions for ${sku(TABLE.key)}` }).click()
  }
  await page.getByRole('button', { name: 'Archive' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Archive' }).click()

  const notice = page.getByRole('region', { name: 'Notifications' }).getByRole('status')
  await expect(notice).toContainText('Product archived')
  const box = await notice.boundingBox()
  expect(box?.x ?? 999).toBeLessThan(40)
  await expect(notice).toBeHidden({ timeout: 8_000 })

  await page.getByLabel('Status').selectOption('ALL')
  if (testInfo.project.name !== 'desktop') {
    await row.getByRole('button', { name: `Actions for ${sku(TABLE.key)}` }).click()
  }
  await row.getByRole('button', { name: 'Restore' }).click()
  await expect(notice).toContainText('Product restored')
})

test('a long-open tab offers a reload when a new version is deployed', async ({
  page,
}, testInfo) => {
  await page.route('**/version.json', (route) =>
    route.fulfill({ contentType: 'application/json', body: '{"build":"e2e-newer"}' }),
  )
  await page.goto('/')
  await expect(page.getByRole('list', { name: 'Products' })).toBeVisible()
  await expect(page.getByText('A new version of this site is available.')).toBeHidden()

  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))

  await expect(page.getByText('A new version of this site is available.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Reload' })).toBeVisible()
  await shot(page, 'new-version', testInfo.project.name)
})

test('the import review is comfortable for long lists', async ({ page }, testInfo) => {
  await asReviewer(page)
  const lines = Array.from(
    { length: 8 },
    (_, index) =>
      `E2E Review ${run} ${index},E2E-${run}-R${index},A long description that keeps going so the text area has something to hold,E2E tests,4.00,1,`,
  )
  const csv = [
    'name,sku,description,category,price,stock,weight_kg',
    `      ,E2E-${run}-BLANK,Name made of spaces,E2E tests,3.00,1,0.1`,
    ...lines,
  ].join('\n')
  await page.goto('/admin/imports/new')
  await page.getByLabel('CSV file', { exact: true }).setInputFiles({
    name: `e2e-${run}-review.csv`,
    mimeType: 'text/csv',
    buffer: Buffer.from(csv),
  })
  await page.getByRole('button', { name: 'Upload and check' }).click()

  const first = page.getByRole('article', { name: 'Line 2' })
  await expect(first.getByText('· marks a space.')).toBeVisible()
  await expect(first.locator('code')).toContainText('······')
  expect(await first.getByLabel('Description').evaluate((field) => field.tagName)).toBe('TEXTAREA')
  const commit = page.getByRole('button', { name: 'Commit import' })
  await expect(commit).toBeDisabled()
  expect(await commit.evaluate((button) => getComputedStyle(button).cursor)).toBe('not-allowed')
  await shot(page, 'import-review', testInfo.project.name)

  await first.getByRole('button', { name: 'Skip this row' }).click()
  await expect(page.getByRole('article', { name: 'Line 3' })).toBeFocused()

  await page.mouse.wheel(0, 4000)
  await expect.poll(async () => Math.round((await commit.boundingBox())?.y ?? 0)).toBeLessThan(140)
  await shot(page, 'import-sticky-bar', testInfo.project.name)

  await page.getByRole('button', { name: 'Discard import' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Discard import' }).click()
  await expect(page.getByText('This import was discarded.')).toBeVisible()
  await expect(page.getByRole('article')).toHaveCount(0)
})

test('the cart has − and + buttons and greys out what cannot be bought', async ({
  page,
}, testInfo) => {
  await page.goto(`/?q=${sku(CART.key)}`)
  await page.getByRole('button', { name: 'Add to cart' }).click()
  await page.getByRole('link', { name: 'Cart: 1 item' }).click()

  const quantity = page.getByLabel(`Quantity of ${CART.name}`)
  const more = page.getByRole('button', { name: `One more ${CART.name}` })
  await expect(page.getByText('Subtotal: $7.50')).toBeVisible()
  await more.click()
  await expect(quantity).toHaveValue('2')
  await expect(page.getByText('Subtotal: $15.00')).toBeVisible()
  await expect(more).toBeDisabled()

  await quantity.fill('5')
  const line = page.getByRole('listitem', { name: CART.name })
  await expect(line.getByText('Only 2 left.')).toBeVisible()
  await expect(line).toHaveAttribute('data-flagged', 'true')
  await expect(page.getByText('Subtotal of available items: $0.00')).toBeVisible()
  await shot(page, 'cart-flagged', testInfo.project.name)

  await line.getByRole('button', { name: 'Use 2' }).click()
  await page.getByRole('button', { name: 'Go to checkout' }).click()
  await expect(page.getByLabel('Expiry (MM/YY)')).toHaveAttribute('placeholder', 'MM/YY')
  await shot(page, 'checkout-expiry', testInfo.project.name)
})

test('no screen is wider than a phone', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'Only on the phone.')
  await asReviewer(page)
  for (const path of [
    '/',
    `/?q=${sku(CART.key)}`,
    '/cart',
    '/admin/products',
    '/admin/products/new',
    '/admin/imports/new',
  ]) {
    await page.goto(path)
    await page.waitForLoadState('networkidle')
    const widths = await page.evaluate(() => ({
      page: document.documentElement.scrollWidth,
      screen: window.visualViewport?.width ?? window.innerWidth,
      layout: window.innerWidth,
    }))
    expect(widths.page, path).toBeLessThanOrEqual(widths.screen)
    expect(widths.layout, path).toBe(widths.screen)
  }
})
