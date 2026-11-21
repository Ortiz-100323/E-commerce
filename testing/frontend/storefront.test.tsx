import { screen, waitFor, within } from '@testing-library/react'
import userEvent, { type UserEvent } from '@testing-library/user-event'
import { http } from 'msw/http'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CART_STORAGE_KEY } from '../../frontend/src/cart/cart'
import { API, serverError } from './support/api'
import { fakeCatalog } from './support/fakeCatalog'
import { expectErrorNotifications } from './support/pageGuard'
import { renderApp } from './support/renderApp'
import { server } from './support/server'

let user: UserEvent

beforeEach(() => {
  user = userEvent.setup()
})

const CATALOG = [
  { sku: 'RS-001', name: 'Running Shoes', category: 'Sports', price: '89.99', stock: 10 },
  { sku: 'TS-002', name: 'Trail Shoes', category: 'Sports', price: '120.00', stock: 0 },
  { sku: 'GK-088', name: 'Gaming Keyboard', category: 'Electronics', price: '129.99', stock: 45 },
  { sku: 'GC-001', name: 'Gift Card', category: 'Gifts', price: '0.00', gift: true, stock: 2 },
  {
    sku: 'OLD-1',
    name: 'Old Shoes',
    category: 'Sports',
    price: '10.00',
    status: 'ARCHIVED' as const,
  },
]

async function names(): Promise<string[]> {
  const grid = await screen.findByRole('list', { name: 'Products' })
  return within(grid)
    .getAllByRole('listitem')
    .map((card) => card.getAttribute('aria-label') ?? '')
}

async function waitForNames(expected: string[]) {
  await waitFor(async () => expect(await names()).toEqual(expected))
}

function cartCount() {
  return screen.getByText(/^Cart: /).textContent
}

describe('the shop search', () => {
  it('lists active products by name, with prices and badges', async () => {
    fakeCatalog(CATALOG)
    renderApp('/')

    await waitForNames(['Gaming Keyboard', 'Gift Card', 'Running Shoes', 'Trail Shoes'])
    const gift = within(screen.getByRole('listitem', { name: 'Gift Card' }))
    expect(gift.getByText('Gift')).toBeInTheDocument()
    expect(gift.getByText('Free')).toBeInTheDocument()
    expect(
      within(screen.getByRole('listitem', { name: 'Trail Shoes' })).getByText('Out of stock'),
    ).toBeInTheDocument()
    expect(
      within(screen.getByRole('listitem', { name: 'Running Shoes' })).getByText('$89.99'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('listitem', { name: 'Old Shoes' })).not.toBeInTheDocument()
    expect(screen.getByText('4 products')).toBeInTheDocument()
  })

  it('updates the results and the URL when searching and filtering', async () => {
    const catalog = fakeCatalog(CATALOG)
    const { router } = renderApp('/')
    await waitForNames(['Gaming Keyboard', 'Gift Card', 'Running Shoes', 'Trail Shoes'])

    await user.type(screen.getByRole('searchbox', { name: 'Search' }), 'shoes')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    await waitForNames(['Running Shoes', 'Trail Shoes'])

    await user.click(screen.getByRole('checkbox', { name: 'In stock only' }))
    await waitForNames(['Running Shoes'])

    await user.selectOptions(screen.getByRole('combobox', { name: 'Sort by' }), '-price')
    expect(router.state.location.search).toBe('?q=shoes&in_stock=true&sort=-price')
    expect(catalog.lists.at(-1)).toMatchObject({
      q: 'shoes',
      in_stock: 'true',
      sort: '-price',
      status: 'ACTIVE',
      page: '1',
      page_size: '12',
    })
  })

  it('filters by category, price range and gifts', async () => {
    fakeCatalog(CATALOG)
    const { router } = renderApp('/')
    await waitForNames(['Gaming Keyboard', 'Gift Card', 'Running Shoes', 'Trail Shoes'])

    await user.selectOptions(await screen.findByRole('combobox', { name: 'Category' }), 'Sports')
    await waitForNames(['Running Shoes', 'Trail Shoes'])

    await user.type(screen.getByLabelText('Min price'), '100')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    await waitForNames(['Trail Shoes'])
    expect(router.state.location.search).toBe('?category=Sports&min_price=100')

    await user.click(screen.getByRole('link', { name: 'Shop' }))
    await user.click(await screen.findByRole('checkbox', { name: 'Gifts only' }))
    await waitForNames(['Gift Card'])
    expect(router.state.location.search).toBe('?tag=GIFT')
  })

  it('keeps the same search after a reload', async () => {
    fakeCatalog(CATALOG)
    const first = renderApp('/?q=shoes&in_stock=true&sort=-price')
    await waitForNames(['Running Shoes'])
    first.unmount()

    renderApp('/?q=shoes&in_stock=true&sort=-price')

    await waitForNames(['Running Shoes'])
    expect(screen.getByRole('searchbox', { name: 'Search' })).toHaveValue('shoes')
    expect(screen.getByRole('checkbox', { name: 'In stock only' })).toBeChecked()
    expect(screen.getByRole('combobox', { name: 'Sort by' })).toHaveValue('-price')
  })

  it('sorts by price and by newest', async () => {
    fakeCatalog(CATALOG)
    renderApp('/?sort=price')

    await waitForNames(['Gift Card', 'Running Shoes', 'Trail Shoes', 'Gaming Keyboard'])
    await user.selectOptions(screen.getByRole('combobox', { name: 'Sort by' }), '-created_at')
    await waitForNames(['Gift Card', 'Gaming Keyboard', 'Trail Shoes', 'Running Shoes'])
  })

  it('pages through the results', async () => {
    fakeCatalog(
      Array.from({ length: 14 }, (_, index) => ({
        sku: `P-${index + 1}`,
        name: `Product ${String(index + 1).padStart(2, '0')}`,
      })),
    )
    const { router } = renderApp('/')

    expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()
    expect(await names()).toHaveLength(12)
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await waitForNames(['Product 13', 'Product 14'])
    expect(router.state.location.search).toBe('?page=2')
  })

  it('moves a page beyond the results back to the last page', async () => {
    fakeCatalog(
      Array.from({ length: 14 }, (_, index) => ({
        sku: `P-${index + 1}`,
        name: `Product ${String(index + 1).padStart(2, '0')}`,
      })),
    )
    const { router } = renderApp('/?page=999')

    await waitForNames(['Product 13', 'Product 14'])
    expect(router.state.location.search).toBe('?page=2')
    expect(screen.getByText('Page 2 of 2')).toBeInTheDocument()
  })

  it('offers to clear the filters when nothing matches', async () => {
    fakeCatalog(CATALOG)
    renderApp('/?q=nothing')

    expect(await screen.findByText(/No products match your search/)).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Clear filters' }))
    await waitForNames(['Gaming Keyboard', 'Gift Card', 'Running Shoes', 'Trail Shoes'])
  })

  it('refuses a price filter that is not a price, without searching', async () => {
    const catalog = fakeCatalog(CATALOG)
    renderApp('/')
    await waitForNames(['Gaming Keyboard', 'Gift Card', 'Running Shoes', 'Trail Shoes'])
    const before = catalog.lists.length

    await user.type(screen.getByLabelText('Min price'), '-5')
    await user.type(screen.getByLabelText('Max price'), 'abc')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(screen.getByLabelText('Min price')).toHaveAccessibleDescription(
      'Use a price like 19.99.',
    )
    expect(screen.getByLabelText('Max price')).toHaveAccessibleDescription(
      'Use a price like 19.99.',
    )
    expect(catalog.lists.length).toBe(before)
  })

  it('refuses a minimum above the maximum, without searching', async () => {
    const catalog = fakeCatalog(CATALOG)
    renderApp('/')
    await waitForNames(['Gaming Keyboard', 'Gift Card', 'Running Shoes', 'Trail Shoes'])
    const before = catalog.lists.length

    await user.type(screen.getByLabelText('Min price'), '50')
    await user.type(screen.getByLabelText('Max price'), '10')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(screen.getByLabelText('Max price')).toHaveAccessibleDescription(
      'The minimum price must not be above the maximum.',
    )
    expect(catalog.lists.length).toBe(before)
  })

  it('ignores bad values typed into the URL instead of failing', async () => {
    const catalog = fakeCatalog(CATALOG)
    renderApp('/?page=abc&sort=colour&tag=SALE&min_price=-1&max_price=x&in_stock=maybe')

    await waitForNames(['Gaming Keyboard', 'Gift Card', 'Running Shoes', 'Trail Shoes'])
    expect(catalog.lists.at(-1)).toEqual({
      status: 'ACTIVE',
      sort: 'name',
      page: '1',
      page_size: '12',
    })
  })

  it('searches for a typed % literally', async () => {
    const catalog = fakeCatalog([
      { sku: 'GK-088', name: 'Gaming Keyboard', description: 'Mechanical, 100% RGB.' },
      { sku: 'RS-001', name: 'Running Shoes' },
    ])
    renderApp('/')
    await waitForNames(['Gaming Keyboard', 'Running Shoes'])

    await user.type(screen.getByRole('searchbox', { name: 'Search' }), '100%')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    await waitForNames(['Gaming Keyboard'])
    expect(catalog.lists.at(-1)?.q).toBe('100%')
  })

  it('offers to try again when the search fails', async () => {
    expectErrorNotifications()
    let attempts = 0
    fakeCatalog(CATALOG)
    server.use(
      http.get(`${API}/products`, () => {
        attempts += 1
        if (attempts <= 3) {
          return serverError('req-shop')
        }
        return undefined
      }),
    )
    renderApp('/')

    expect(await screen.findByText(/We couldn't load the products/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    await waitForNames(['Gaming Keyboard', 'Gift Card', 'Running Shoes', 'Trail Shoes'])
  })
})

describe('the product page and the cart', () => {
  async function openProduct(name: string) {
    await user.click(await screen.findByRole('link', { name }))
    return screen.findByRole('heading', { level: 1, name })
  }

  it('shows the product and adds it to the cart', async () => {
    fakeCatalog(CATALOG)
    renderApp('/')
    await openProduct('Running Shoes')

    expect(screen.getByText('$89.99')).toBeInTheDocument()
    expect(screen.getByText('10 in stock')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Add to cart' }))

    expect(screen.getByRole('status')).toHaveTextContent('Added to cart (1 in your cart).')
    expect(cartCount()).toBe('Cart: 1 item')
    expect(JSON.parse(window.localStorage.getItem(CART_STORAGE_KEY) ?? '[]')).toEqual([
      expect.objectContaining({ sku: 'RS-001', price: '89.99', quantity: 1 }),
    ])
  })

  it('cannot add an out-of-stock product to the cart', async () => {
    fakeCatalog(CATALOG)
    renderApp('/')
    await openProduct('Trail Shoes')

    expect(screen.getByText('Out of stock', { selector: 'dd' })).toBeInTheDocument()
    const button = screen.getByRole('button', { name: 'Out of stock' })
    expect(button).toBeDisabled()
    await user.click(button)
    expect(cartCount()).toBe('Cart: 0 items')
  })

  it('never adds more than the stock, even with fast clicks', async () => {
    fakeCatalog(CATALOG)
    renderApp('/')
    await openProduct('Gift Card')
    expect(screen.getByText('Free')).toBeInTheDocument()

    await user.tripleClick(screen.getByRole('button', { name: 'Add to cart' }))

    expect(screen.getByRole('button', { name: 'Only 2 in stock' })).toBeDisabled()
    expect(cartCount()).toBe('Cart: 2 items')
  })

  it('keeps the cart after a reload', async () => {
    fakeCatalog(CATALOG)
    const first = renderApp('/')
    await openProduct('Running Shoes')
    await user.click(screen.getByRole('button', { name: 'Add to cart' }))
    first.unmount()

    renderApp('/')
    await screen.findByRole('list', { name: 'Products' })
    expect(cartCount()).toBe('Cart: 1 item')
  })

  it('works for the session when storage is blocked', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    fakeCatalog(CATALOG)
    const first = renderApp('/')
    await openProduct('Running Shoes')
    await user.click(screen.getByRole('button', { name: 'Add to cart' }))
    first.unmount()

    renderApp('/')
    await screen.findByRole('list', { name: 'Products' })
    expect(cartCount()).toBe('Cart: 1 item')
  })

  it('says an archived product is no longer available', async () => {
    const catalog = fakeCatalog(CATALOG)
    renderApp(`/products/${catalog.bySku('OLD-1')?.id}`)

    expect(await screen.findByText('This product is no longer available.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'No longer available' })).toBeDisabled()
  })

  it('says a product that does not exist was not found, without a pop-up', async () => {
    fakeCatalog(CATALOG)
    renderApp('/products/00000000-0000-4000-8000-999999999999')

    expect(await screen.findByRole('heading', { name: 'Product not found' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to the shop' })).toHaveAttribute('href', '/')
  })
})
