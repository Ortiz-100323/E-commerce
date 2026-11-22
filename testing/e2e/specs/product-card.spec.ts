import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test'

import { archiveAll, createProduct, runId } from './support'

const PIXEL = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  'base64',
)
const IMAGE_HOST = 'https://images.e2e.test'

type Seed = { key: string; name: string; category: string; price: string; stock: number }

const run = runId()
const sku = (key: string) => `E2E-${run}-${key}`
const SEEDS: Seed[] = [
  { key: 'SPKA', name: `E2E Speaker ${run}`, category: 'Electronics', price: '59.99', stock: 40 },
  { key: 'SPKB', name: `E2E Speaker ${run}`, category: 'Electronics', price: '24.99', stock: 2 },
  { key: 'TENT', name: `E2E Tent ${run}`, category: 'Outdoors', price: '199.99', stock: 0 },
  {
    key: 'LONG',
    name: `E2E Desk lamp with an unusually long name that keeps going past two lines ${run}`,
    category: 'Home & Office',
    price: '34.50',
    stock: 12,
  },
  { key: 'GIFT', name: `E2E Gift ${run}`, category: 'Gifts', price: '0.00', stock: 7 },
  { key: 'BROKEN', name: `E2E Kettle ${run}`, category: 'Kitchen', price: '15.00', stock: 9 },
]
const IMAGES: Record<string, string> = {
  SPKA: `${IMAGE_HOST}/${run}-speaker.png`,
  BROKEN: `${IMAGE_HOST}/${run}-missing.png`,
}

let api: APIRequestContext

test.beforeAll(async ({ playwright }, testInfo) => {
  api = await playwright.request.newContext({ baseURL: testInfo.project.use.baseURL })
  for (const seed of SEEDS) {
    await createProduct(api, sku(seed.key), seed.name, seed.price, seed.stock, {
      category: seed.category,
      image_url: IMAGES[seed.key] ?? null,
    })
  }
})

test.afterAll(async () => {
  await archiveAll(
    api,
    SEEDS.map((seed) => sku(seed.key)),
  )
  await api.dispose()
})

async function openGrid(page: Page) {
  await page.route(`${IMAGE_HOST}/**`, (route) =>
    route.request().url().includes('missing')
      ? route.fulfill({ status: 404 })
      : route.fulfill({ status: 200, contentType: 'image/png', body: PIXEL }),
  )
  await page.goto(`/?q=E2E-${run}`)
  await expect(page.getByText('6 products')).toBeVisible()
}

const TWINS = new Set(['SPKA', 'SPKB'])

function card(page: Page, key: string): Locator {
  const seed = SEEDS.find((item) => item.key === key)
  return TWINS.has(key)
    ? page.getByRole('listitem', { name: new RegExp(`SKU ${sku(key)}$`) })
    : page.getByRole('listitem', { name: seed?.name, exact: true })
}

function cartLink(page: Page): Locator {
  return page.getByRole('link', { name: /^Cart: / })
}

test('every card has a 4:3 image area, at most two lines of name and the same height', async ({
  page,
}, testInfo) => {
  await openGrid(page)
  const cards = page.getByRole('list', { name: 'Products' }).getByRole('listitem')
  await expect(cards).toHaveCount(6)

  const heights: number[] = []
  for (const item of await cards.all()) {
    const box = await item.boundingBox()
    const media = await item.locator(':scope > div').first().boundingBox()
    expect(box).not.toBeNull()
    expect(media).not.toBeNull()
    heights.push(Math.round(box?.height ?? 0))
    expect((media?.width ?? 0) / (media?.height ?? 1)).toBeCloseTo(4 / 3, 1)
  }
  expect(Math.max(...heights) - Math.min(...heights)).toBeLessThanOrEqual(1)

  const longName = card(page, 'LONG').getByRole('heading')
  const lines = await longName.evaluate((element) => {
    const style = getComputedStyle(element)
    return element.getBoundingClientRect().height / Number.parseFloat(style.lineHeight)
  })
  expect(lines).toBeLessThanOrEqual(2.05)
  await expect(longName).toHaveAttribute('title', SEEDS[3].name)

  await page.screenshot({
    path: `results/evidence/${testInfo.project.name}-cards.png`,
    fullPage: true,
  })
})

test('a photo is shown when there is one, the category placeholder otherwise', async ({ page }) => {
  await openGrid(page)

  const photo = card(page, 'SPKA').locator('img')
  await expect(photo).toBeVisible()
  expect(await photo.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0)
  await expect(card(page, 'SPKB').locator('[data-placeholder="Electronics"] svg')).toBeVisible()
  await expect(card(page, 'BROKEN').locator('[data-placeholder="Kitchen"]')).toBeVisible()
  await expect(card(page, 'BROKEN').locator('img')).toHaveCount(0)
})

test('look-alikes are told apart and stock is shown honestly', async ({ page }) => {
  await openGrid(page)

  await expect(card(page, 'SPKA').getByText(`SKU ${sku('SPKA')}`)).toBeVisible()
  await expect(card(page, 'SPKB').getByText(`SKU ${sku('SPKB')}`)).toBeVisible()
  await expect(card(page, 'TENT').getByText(/^SKU /)).toHaveCount(0)
  await expect(card(page, 'LONG').getByText('In stock')).toBeVisible()
  await expect(card(page, 'SPKB').getByText('Only 2 left')).toBeVisible()
  await expect(card(page, 'TENT').getByText('Out of stock')).toBeVisible()
  await expect(card(page, 'TENT').getByRole('button', { name: 'Add to cart' })).toBeDisabled()
  await expect(card(page, 'GIFT').getByText('Free')).toBeVisible()
})

test('Add to cart works on the card and stops at the stock', async ({ page }) => {
  await openGrid(page)
  const low = card(page, 'SPKB')

  await low.getByRole('button', { name: 'Add to cart' }).click()
  await expect(cartLink(page)).toHaveText('Cart: 1 item')
  await low.getByRole('button', { name: /Add to cart|Added/ }).click()

  await expect(cartLink(page)).toHaveText('Cart: 2 items')
  await expect(low.getByRole('button', { name: 'All 2 in your cart' })).toBeDisabled()
  await expect(page).toHaveURL(new RegExp(`q=E2E-${run}`))
})

test('clicking the card outside the button opens the product page', async ({ page }) => {
  await openGrid(page)

  const media = await card(page, 'GIFT').locator(':scope > div').first().boundingBox()
  await page.mouse.click((media?.x ?? 0) + (media?.width ?? 0) / 2, (media?.y ?? 0) + 20)

  await expect(page).toHaveURL(/\/products\/[0-9a-f-]{36}$/)
  await expect(page.getByRole('heading', { level: 1, name: SEEDS[4].name })).toBeVisible()
})

test('the card works with the keyboard alone', async ({ page }) => {
  await openGrid(page)
  const gift = card(page, 'GIFT')
  const link = gift.getByRole('link', { name: SEEDS[4].name })
  const button = gift.getByRole('button', { name: 'Add to cart' })

  await link.focus()
  await page.keyboard.press('Tab')
  await expect(button).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(cartLink(page)).toHaveText('Cart: 1 item')
  await page.keyboard.press('Space')
  await expect(cartLink(page)).toHaveText('Cart: 2 items')

  await page.keyboard.press('Shift+Tab')
  await expect(link).toBeFocused()
  expect(await gift.evaluate((element) => getComputedStyle(element).outlineStyle)).toBe('solid')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(new RegExp('/products/'))
})

test('hovering lifts the card on a desktop', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Touch screens have no hover.')
  await openGrid(page)
  const target = card(page, 'SPKA')

  await target.hover()

  await expect
    .poll(() => target.evaluate((element) => getComputedStyle(element).transform))
    .not.toBe('none')
})

test('a phone shows two columns with large touch targets', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'Only on the phone.')
  await openGrid(page)
  const cards = await page.getByRole('list', { name: 'Products' }).getByRole('listitem').all()
  const boxes = await Promise.all(cards.map((item) => item.boundingBox()))

  const columns = new Set(boxes.map((box) => Math.round(box?.x ?? 0)))
  expect(columns.size).toBe(2)
  const button = await card(page, 'SPKA').getByRole('button').boundingBox()
  expect(button?.height ?? 0).toBeGreaterThanOrEqual(44)
  await page.screenshot({
    path: `results/evidence/${testInfo.project.name}-two-columns.png`,
    fullPage: true,
  })
})

test('the real catalog with the new cards', async ({ page }, testInfo) => {
  await page.goto('/')
  await expect(
    page.getByRole('list', { name: 'Products' }).getByRole('listitem').first(),
  ).toBeVisible()

  await page.screenshot({ path: `results/evidence/${testInfo.project.name}-shop.png` })
})

test('the product page puts the picture beside the details, or above them on a phone', async ({
  page,
}, testInfo) => {
  await openGrid(page)
  await card(page, 'SPKA').getByRole('link').click()
  const heading = page.getByRole('heading', { level: 1, name: SEEDS[0].name })
  await expect(heading).toBeVisible()

  const picture = await page.locator('article img').first().boundingBox()
  const title = await heading.boundingBox()
  expect(picture).not.toBeNull()
  expect(title).not.toBeNull()
  if (testInfo.project.name === 'desktop') {
    expect((picture?.x ?? 0) + (picture?.width ?? 0)).toBeLessThanOrEqual(title?.x ?? 0)
  } else {
    expect((picture?.y ?? 0) + (picture?.height ?? 0)).toBeLessThanOrEqual(title?.y ?? 0)
  }
  await expect(page.getByRole('button', { name: 'Add to cart' })).toBeVisible()
  await page.screenshot({
    path: `results/evidence/${testInfo.project.name}-product-page.png`,
    fullPage: true,
  })
})

test('an empty search explains what to do next', async ({ page }, testInfo) => {
  await page.goto(`/?q=nothing-${run}`)

  await expect(page.getByRole('heading', { name: 'No products match your search' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Clear filters' })).toBeVisible()
  await page.screenshot({ path: `results/evidence/${testInfo.project.name}-empty.png` })
})

test('a phone folds the filters behind a button, a desktop shows them', async ({
  page,
}, testInfo) => {
  await page.goto(`/?q=E2E-${run}&in_stock=true`)
  const category = page.getByRole('combobox', { name: 'Category' })
  const toggle = page.getByRole('button', { name: 'Filters (1)' })

  if (testInfo.project.name === 'desktop') {
    await expect(category).toBeVisible()
    await expect(toggle).toBeHidden()
    return
  }
  await expect(category).toBeHidden()
  await toggle.click()
  await expect(category).toBeVisible()
  await expect(page.getByRole('checkbox', { name: 'In stock only' })).toBeChecked()
  await page.screenshot({ path: `results/evidence/${testInfo.project.name}-filters-open.png` })
})

test('the other screens use the same buttons, fields and colours', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'One device is enough for the screen tour.')
  await page.addInitScript(() => window.localStorage.setItem('ecommerce.actor', 'E2E reviewer'))
  const shots: [string, string, string][] = [
    ['/admin/products', 'Products', 'admin-products'],
    ['/admin/products/new', 'New product', 'admin-new-product'],
    ['/admin/imports/new', 'Import products from a CSV file', 'admin-import'],
  ]
  for (const [path, heading, name] of shots) {
    await page.goto(path)
    await expect(page.getByRole('heading', { name: heading })).toBeVisible()
    await page.screenshot({ path: `results/evidence/${testInfo.project.name}-${name}.png` })
  }

  await openGrid(page)
  await card(page, 'LONG').getByRole('button', { name: 'Add to cart' }).click()
  await page.getByRole('link', { name: 'Cart: 1 item' }).click()
  await expect(page.getByRole('heading', { name: 'Your cart' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Go to checkout' })).toBeEnabled()
  await page.screenshot({ path: `results/evidence/${testInfo.project.name}-cart.png` })
  await page.getByRole('button', { name: 'Go to checkout' }).click()
  await expect(page.getByRole('heading', { name: 'Checkout' })).toBeVisible()
  await page.screenshot({
    path: `results/evidence/${testInfo.project.name}-checkout.png`,
    fullPage: true,
  })
})
