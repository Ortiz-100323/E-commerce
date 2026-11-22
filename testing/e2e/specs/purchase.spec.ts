import { expect, test } from '@playwright/test'

import {
  APPROVED,
  archiveAll,
  checkOut,
  logInAsAdmin,
  createProduct,
  DECLINED,
  productBySku,
  runId,
} from './support'

const created: string[] = []

test.afterEach(async ({ request }) => {
  await archiveAll(request, created.splice(0))
})

test('an imported product is found in the shop, bought, and its stock goes down', async ({
  page,
  request,
}) => {
  const run = runId()
  const lamp = { sku: `E2E-${run}-LAMP`, name: `E2E Lamp ${run}` }
  const gift = { sku: `E2E-${run}-GIFT`, name: `E2E Gift ${run}` }
  created.push(lamp.sku, gift.sku)
  const csv = [
    'name,sku,description,category,price,stock,weight_kg',
    `${lamp.name},${lamp.sku},A lamp for the browser test,E2E tests,12.50,5,0.4`,
    `${gift.name},${gift.sku},A free gift for the browser test,E2E tests,0.00,3,0.1`,
  ].join('\n')

  await logInAsAdmin(page)
  await page.goto('/admin/imports/new')
  await page.getByLabel('CSV file', { exact: true }).setInputFiles({
    name: `e2e-${run}.csv`,
    mimeType: 'text/csv',
    buffer: Buffer.from(csv),
  })
  await page.getByRole('button', { name: 'Upload and check' }).click()
  await expect(page.getByRole('heading', { name: `Review import: e2e-${run}.csv` })).toBeVisible()
  await page
    .getByRole('article', { name: 'Line 3' })
    .getByRole('button', { name: 'Confirm as free gift' })
    .click()
  const commit = page.getByRole('button', { name: 'Commit import' })
  await expect(commit).toBeEnabled()
  await commit.click()
  await expect(page.getByRole('status')).toContainText('Imported. 2 created, 0 updated, 0 skipped.')

  await page.goto('/')
  await page.getByPlaceholder('What are you looking for?').fill(lamp.name)
  await page.getByRole('button', { name: 'Search' }).click()
  await page.getByRole('listitem', { name: lamp.name }).getByRole('link').first().click()
  await page.getByRole('button', { name: 'Add to cart' }).click()
  await page.getByRole('button', { name: 'Add to cart' }).click()
  await page.getByRole('link', { name: 'Cart: 2 items' }).click()
  await expect(page.getByText('Subtotal: $25.00')).toBeVisible()
  await checkOut(page, APPROVED)
  await page.getByRole('button', { name: 'Pay $25.00' }).click()

  await expect(page.getByRole('heading', { name: 'Thank you, E2E test' })).toBeVisible()
  await expect(page.getByText('Paid with the card ending in 4242.')).toBeVisible()
  expect((await productBySku(request, lamp.sku)).stock).toBe(3)
  expect((await productBySku(request, gift.sku)).stock).toBe(3)
})

test('a declined card leaves the stock unchanged', async ({ page, request }) => {
  const run = runId()
  const sku = `E2E-${run}-DECL`
  created.push(sku)
  const product = await createProduct(request, sku, `E2E Kettle ${run}`, '30.00', 5)

  await page.goto(`/products/${product.id}`)
  await page.getByRole('button', { name: 'Add to cart' }).click()
  await page.getByRole('link', { name: 'Cart: 1 item' }).click()
  await checkOut(page, DECLINED)
  await page.getByRole('button', { name: 'Pay $30.00' }).click()

  await expect(page.getByRole('alert')).toContainText('Your card was declined.')
  await expect(page.getByLabel('Card number')).toHaveValue('')
  expect((await productBySku(request, sku)).stock).toBe(5)
})

test('a double click on Pay buys only once', async ({ page, request }) => {
  const run = runId()
  const sku = `E2E-${run}-TWICE`
  created.push(sku)
  const product = await createProduct(request, sku, `E2E Mug ${run}`, '8.00', 5)

  await page.goto(`/products/${product.id}`)
  await page.getByRole('button', { name: 'Add to cart' }).click()
  await page.getByRole('link', { name: 'Cart: 1 item' }).click()
  await checkOut(page, APPROVED)
  await page.getByRole('button', { name: 'Pay $8.00' }).dblclick()

  await expect(page.getByRole('heading', { name: 'Thank you, E2E test' })).toBeVisible()
  expect((await productBySku(request, sku)).stock).toBe(4)
})
