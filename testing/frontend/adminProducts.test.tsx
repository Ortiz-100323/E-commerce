import { screen, waitFor, within } from '@testing-library/react'
import userEvent, { type UserEvent } from '@testing-library/user-event'
import { type QueryClient, useQueryClient } from '@tanstack/react-query'
import { delay } from 'msw'
import { http, HttpResponse } from 'msw/http'
import { beforeEach, describe, expect, it } from 'vitest'

import { ACTOR_STORAGE_KEY } from '../../frontend/src/actor/actorStorage'
import { AppShell } from '../../frontend/src/app/AppShell'
import { AdminLayout } from '../../frontend/src/features/admin/AdminLayout'
import { EditProductPage } from '../../frontend/src/features/admin/products/ProductFormPages'
import { API, serverError, validationProblem } from './support/api'
import { fakeCatalog } from './support/fakeCatalog'
import { expectErrorNotifications } from './support/pageGuard'
import { renderApp } from './support/renderApp'
import { server } from './support/server'

let user: UserEvent

beforeEach(() => {
  user = userEvent.setup()
})

function asReviewer(name = 'Maria') {
  window.localStorage.setItem(ACTOR_STORAGE_KEY, name)
}

async function table() {
  return within(await screen.findByRole('table'))
}

async function row(sku: string) {
  return within(await screen.findByRole('row', { name: sku }))
}

function notifications() {
  return within(screen.getByRole('region', { name: 'Notifications' }))
}

async function fill(label: string, value: string) {
  const input = screen.getByLabelText(label)
  await user.clear(input)
  if (value) {
    await user.type(input, value)
  }
}

async function fillNewProduct(values: Record<string, string>) {
  await screen.findByRole('heading', { name: 'New product' })
  for (const [label, value] of Object.entries(values)) {
    await fill(label, value)
  }
}

const runningShoes = {
  SKU: 'rs-001',
  Name: 'Running Shoes',
  Category: 'Sports',
  'Price (USD)': '89.99',
  Stock: '10',
  'Weight (kg)': '0.8',
}

describe('the products table', () => {
  it('lists active products with price, stock and badges', async () => {
    asReviewer()
    fakeCatalog([
      { sku: 'RS-001', name: 'Running Shoes', category: 'Sports', price: '89.99', stock: 10 },
      { sku: 'GC-001', name: 'Gift Card', category: 'Gifts', price: '0.00', gift: true, stock: 0 },
      { sku: 'OLD-1', name: 'Old Thing', status: 'ARCHIVED' },
    ])
    renderApp('/admin/products')

    const rows = (await table()).getAllByRole('row').slice(1)
    expect(rows.map((item) => item.getAttribute('aria-label'))).toEqual(['GC-001', 'RS-001'])
    const gift = await row('GC-001')
    expect(gift.getByText('Gift')).toBeInTheDocument()
    expect(gift.getByText('$0.00')).toBeInTheDocument()
    expect(gift.getByText('Out of stock')).toBeInTheDocument()
    expect((await row('RS-001')).getByText('$89.99')).toBeInTheDocument()
    expect(screen.getByText('Page 1 of 1 · 2 products')).toBeInTheDocument()
  })

  it('searches and filters by status, keeping both in the address', async () => {
    asReviewer()
    fakeCatalog([
      { sku: 'RS-001', name: 'Running Shoes' },
      { sku: 'TS-002', name: 'Trail Shoes' },
      { sku: 'GK-088', name: 'Gaming Keyboard' },
      { sku: 'OLD-1', name: 'Old Shoes', status: 'ARCHIVED' },
    ])
    const { router } = renderApp('/admin/products')
    await row('GK-088')

    await user.type(screen.getByRole('searchbox', { name: 'Search' }), 'shoes')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() =>
      expect(screen.queryByRole('row', { name: 'GK-088' })).not.toBeInTheDocument(),
    )
    expect(screen.getByRole('row', { name: 'RS-001' })).toBeInTheDocument()
    expect(screen.getByRole('row', { name: 'TS-002' })).toBeInTheDocument()

    await user.selectOptions(screen.getByRole('combobox', { name: 'Status' }), 'ALL')
    expect(await screen.findByRole('row', { name: 'OLD-1' })).toBeInTheDocument()
    expect(router.state.location.search).toBe('?q=shoes&status=ALL')
  })

  it('says so when nothing matches', async () => {
    asReviewer()
    fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes' }])
    renderApp('/admin/products?q=nothing')

    expect(await screen.findByText('No products match.')).toBeInTheDocument()
  })

  it('pages through the products', async () => {
    asReviewer()
    fakeCatalog(
      Array.from({ length: 25 }, (_, index) => ({
        sku: `P-${String(index + 1).padStart(2, '0')}`,
        name: `Product ${String(index + 1).padStart(2, '0')}`,
      })),
    )
    renderApp('/admin/products')

    expect(await screen.findByText('Page 1 of 2 · 25 products')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Page 2 of 2 · 25 products')).toBeInTheDocument()
    expect(screen.getByRole('row', { name: 'P-25' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })

  it('moves a page beyond the results back to the last page', async () => {
    asReviewer()
    fakeCatalog(
      Array.from({ length: 25 }, (_, index) => ({
        sku: `P-${String(index + 1).padStart(2, '0')}`,
        name: `Product ${String(index + 1).padStart(2, '0')}`,
      })),
    )
    const { router } = renderApp('/admin/products?page=999')

    expect(await screen.findByText('Page 2 of 2 · 25 products')).toBeInTheDocument()
    expect(screen.getByRole('row', { name: 'P-25' })).toBeInTheDocument()
    expect(router.state.location.search).toBe('?page=2')
  })

  it('offers to try again when the products cannot be loaded', async () => {
    expectErrorNotifications()
    asReviewer()
    let attempts = 0
    server.use(
      http.get(`${API}/products`, () => {
        attempts += 1
        return attempts <= 3
          ? serverError('req-list')
          : HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 })
      }),
    )
    renderApp('/admin/products')

    expect(await screen.findByText(/We couldn't load the products/)).toBeInTheDocument()
    expect(notifications().getByText('Reference: req-list')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('No products match.')).toBeInTheDocument()
  })
})

describe('creating, editing, archiving and restoring', () => {
  it('creates a product and shows it in the table, with the reviewer recorded', async () => {
    asReviewer('Łukasz')
    const catalog = fakeCatalog()
    const { router } = renderApp('/admin/products')

    await user.click(await screen.findByRole('link', { name: 'New product' }))
    await fillNewProduct(runningShoes)
    await user.click(screen.getByRole('button', { name: 'Create product' }))

    expect(await screen.findByRole('row', { name: 'RS-001' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/admin/products')
    expect(notifications().getByText('Product created')).toBeInTheDocument()
    expect(catalog.requests).toEqual([
      {
        method: 'POST',
        path: '/api/v1/products',
        actor: '%C5%81ukasz',
        body: {
          sku: 'rs-001',
          name: 'Running Shoes',
          description: '',
          category: 'Sports',
          price: '89.99',
          stock: 10,
          weight_kg: '0.8',
          gift: false,
        },
      },
    ])
  })

  it('edits a product and the table shows the new values', async () => {
    asReviewer()
    const catalog = fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes', price: '89.99' }])
    renderApp('/admin/products')

    await user.click((await row('RS-001')).getByRole('link', { name: 'Edit' }))
    await screen.findByRole('heading', { name: 'Edit Running Shoes' })
    expect(screen.getByLabelText('SKU')).toHaveAttribute('readonly')
    await fill('Price (USD)', '79.99')
    await fill('Name', 'Trail Shoes')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    const updated = await row('RS-001')
    expect(updated.getByText('Trail Shoes')).toBeInTheDocument()
    expect(updated.getByText('$79.99')).toBeInTheDocument()
    expect(notifications().getByText('Changes saved')).toBeInTheDocument()
    expect(catalog.requests[0]).toMatchObject({
      method: 'PUT',
      body: { version: 1, price: '79.99' },
    })
    expect(catalog.bySku('RS-001')?.version).toBe(2)
  })

  it('archives after confirmation and restores, and the table follows', async () => {
    asReviewer()
    const catalog = fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes' }])
    renderApp('/admin/products?status=ALL')

    await user.click((await row('RS-001')).getByRole('button', { name: 'Archive' }))
    const dialog = screen.getByRole('alertdialog', { name: 'Archive Running Shoes?' })
    await user.click(within(dialog).getByRole('button', { name: 'Archive' }))

    expect(await (await row('RS-001')).findByText('Archived')).toBeInTheDocument()
    expect(notifications().getByText('Product archived')).toBeInTheDocument()

    await user.click((await row('RS-001')).getByRole('button', { name: 'Restore' }))
    expect(await (await row('RS-001')).findByText('Active')).toBeInTheDocument()
    expect(catalog.requests.map((request) => request.method)).toEqual(['DELETE', 'POST'])
    expect(catalog.bySku('RS-001')?.status).toBe('ACTIVE')
  })

  it('sends nothing when the archive is cancelled', async () => {
    asReviewer()
    const catalog = fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes' }])
    renderApp('/admin/products')

    await user.click((await row('RS-001')).getByRole('button', { name: 'Archive' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(catalog.requests).toEqual([])
  })

  it('sends one archive request when the confirmation is clicked twice', async () => {
    asReviewer()
    let deletes = 0
    fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes' }])
    server.use(
      http.delete(`${API}/products/:id`, async () => {
        deletes += 1
        await delay(50)
        return HttpResponse.json({})
      }),
    )
    renderApp('/admin/products')

    await user.click((await row('RS-001')).getByRole('button', { name: 'Archive' }))
    const confirm = within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Archive' })
    await user.dblClick(confirm)

    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument())
    expect(deletes).toBe(1)
  })
})

describe('the gift confirmation', () => {
  it('asks before saving a price of 0, and refusing keeps the form open without sending', async () => {
    asReviewer()
    const catalog = fakeCatalog()
    const { router } = renderApp('/admin/products/new')
    await fillNewProduct({ ...runningShoes, SKU: 'GC-001', Name: 'Gift Card', 'Price (USD)': '0' })

    await user.click(screen.getByRole('button', { name: 'Create product' }))
    const dialog = screen.getByRole('alertdialog', {
      name: 'Price is 0. Mark this product as a gift?',
    })
    await user.click(within(dialog).getByRole('button', { name: 'No, go back' }))

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'New product' })).toBeInTheDocument()
    expect(screen.getByLabelText('Price (USD)')).toHaveFocus()
    expect(screen.getByLabelText('Name')).toHaveValue('Gift Card')
    expect(router.state.location.pathname).toBe('/admin/products/new')
    expect(catalog.requests).toEqual([])
  })

  it('saves the product as a gift when confirmed', async () => {
    asReviewer()
    const catalog = fakeCatalog()
    renderApp('/admin/products/new')
    await fillNewProduct({
      ...runningShoes,
      SKU: 'GC-001',
      Name: 'Gift Card',
      'Price (USD)': '0.00',
    })

    await user.click(screen.getByRole('button', { name: 'Create product' }))
    await user.click(screen.getByRole('button', { name: 'Yes, mark as gift' }))

    const created = await row('GC-001')
    expect(created.getByText('Gift')).toBeInTheDocument()
    expect(catalog.requests[0].body).toMatchObject({ price: '0.00', gift: true })
  })

  it('does not ask when the gift box is already ticked', async () => {
    asReviewer()
    const catalog = fakeCatalog()
    renderApp('/admin/products/new')
    await fillNewProduct({ ...runningShoes, SKU: 'GC-001', 'Price (USD)': '0' })
    await user.click(screen.getByRole('checkbox', { name: /Free gift/ }))

    await user.click(screen.getByRole('button', { name: 'Create product' }))

    expect(await screen.findByRole('row', { name: 'GC-001' })).toBeInTheDocument()
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(catalog.requests).toHaveLength(1)
  })

  it('puts the gift option first, and ticking it sets the price to 0 and locks it', async () => {
    asReviewer()
    const catalog = fakeCatalog()
    renderApp('/admin/products/new')
    await fillNewProduct({ ...runningShoes, SKU: 'GF-003', Name: 'Gift Wrap', 'Price (USD)': '55' })
    const gift = screen.getByRole('checkbox', { name: /Free gift/ })
    const fields = screen.getAllByRole('textbox')
    expect(gift.compareDocumentPosition(fields[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

    await user.click(gift)

    const price = screen.getByLabelText('Price (USD)')
    expect(price).toHaveValue('0')
    expect(price).toHaveAttribute('readonly')
    expect(price).toHaveAccessibleDescription('Gifts are always free.')
    await user.click(screen.getByRole('button', { name: 'Create product' }))
    expect(await screen.findByRole('row', { name: 'GF-003' })).toBeInTheDocument()
    expect(catalog.requests[0].body).toMatchObject({ price: '0', gift: true })
  })

  it('brings the previous price back when the gift option is unticked', async () => {
    asReviewer()
    fakeCatalog()
    renderApp('/admin/products/new')
    await fillNewProduct({ ...runningShoes, 'Price (USD)': '55' })
    const gift = screen.getByRole('checkbox', { name: /Free gift/ })

    await user.click(gift)
    await user.click(gift)

    const price = screen.getByLabelText('Price (USD)')
    expect(price).toHaveValue('55')
    expect(price).not.toHaveAttribute('readonly')
  })

  it('shows the server refusing a paid gift on the price field', async () => {
    asReviewer()
    fakeCatalog([{ sku: 'SP-003', name: 'Normal shoes', price: '55.00' }])
    server.use(
      http.put(`${API}/products/:id`, () =>
        validationProblem([
          {
            field: 'price',
            code: 'gift_must_be_free',
            message: 'A gift must be free. Set the price to 0, or untick the gift.',
          },
        ]),
      ),
    )
    renderApp('/admin/products')
    await user.click((await row('SP-003')).getByRole('link', { name: 'Edit' }))
    await screen.findByRole('heading', { name: 'Edit Normal shoes' })

    await fill('Name', 'Normal shoes v2')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByText(/A gift must be free/)).toBeInTheDocument()
    expect(screen.getByLabelText('Price (USD)')).toHaveAttribute('aria-invalid', 'true')
  })

  it('asks again when the gift box is unticked on a free product', async () => {
    asReviewer()
    const catalog = fakeCatalog([{ sku: 'GC-001', name: 'Gift Card', price: '0.00', gift: true }])
    renderApp('/admin/products')
    await user.click((await row('GC-001')).getByRole('link', { name: 'Edit' }))
    await screen.findByRole('heading', { name: 'Edit Gift Card' })

    await user.click(screen.getByRole('checkbox', { name: /Free gift/ }))
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(
      screen.getByRole('alertdialog', { name: 'Price is 0. Mark this product as a gift?' }),
    ).toBeInTheDocument()
    expect(catalog.requests).toEqual([])
  })
})

describe('errors on the form', () => {
  it('shows the browser checks before sending anything', async () => {
    asReviewer()
    const catalog = fakeCatalog()
    renderApp('/admin/products/new')
    await fillNewProduct({ 'Price (USD)': '1.234', Stock: '-1', 'Weight (kg)': 'abc' })

    await user.click(screen.getByRole('button', { name: 'Create product' }))

    expect(await screen.findByText('SKU is required.')).toBeInTheDocument()
    expect(screen.getByText('Name is required.')).toBeInTheDocument()
    expect(screen.getByText('Category is required.')).toBeInTheDocument()
    expect(screen.getByLabelText('Price (USD)')).toHaveAccessibleDescription(
      'Use a number with at most 2 decimals, like 19.99.',
    )
    expect(screen.getByLabelText('Stock')).toHaveAccessibleDescription(
      'Use a whole number of 0 or more.',
    )
    expect(screen.getByLabelText('Weight (kg)')).toHaveAccessibleDescription(
      'Use a number with at most 3 decimals, like 0.250.',
    )
    expect(catalog.requests).toEqual([])
  })

  it('puts the server validation errors on the matching fields', async () => {
    asReviewer()
    fakeCatalog()
    renderApp('/admin/products/new')
    await fillNewProduct({ ...runningShoes, Name: '<b>Shoes</b>' })

    await user.click(screen.getByRole('button', { name: 'Create product' }))

    const name = screen.getByLabelText('Name')
    await waitFor(() => expect(name).toHaveAttribute('aria-invalid', 'true'))
    expect(name).toHaveAccessibleDescription('Remove < and > from the name.')
    expect(name).toHaveFocus()
    expect(screen.getByLabelText('SKU')).toHaveValue('rs-001')
    expect(notifications().queryByRole('alert')).not.toBeInTheDocument()
  })

  it('puts a duplicate SKU on the SKU field without a pop-up', async () => {
    asReviewer()
    fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes' }])
    renderApp('/admin/products/new')
    await fillNewProduct(runningShoes)

    await user.click(screen.getByRole('button', { name: 'Create product' }))

    expect(await screen.findByText('SKU RS-001 is already taken.')).toBeInTheDocument()
    expect(screen.getByLabelText('SKU')).toHaveAttribute('aria-invalid', 'true')
    expect(notifications().queryByRole('alert')).not.toBeInTheDocument()
  })

  it('never overwrites a change made by someone else, even after a background refresh', async () => {
    asReviewer()
    const catalog = fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes', price: '89.99' }])
    const grabbed: { client?: QueryClient } = {}
    function GrabClient() {
      grabbed.client = useQueryClient()
      return null
    }
    const editRoutes = [
      {
        element: <AppShell />,
        children: [
          {
            path: 'admin',
            element: <AdminLayout />,
            children: [
              {
                path: 'products/:productId/edit',
                element: (
                  <>
                    <EditProductPage />
                    <GrabClient />
                  </>
                ),
              },
              { path: 'products', element: <p>Table</p> },
            ],
          },
        ],
      },
    ]
    const id = catalog.bySku('RS-001')?.id
    renderApp(`/admin/products/${id}/edit`, { routes: editRoutes })
    await screen.findByRole('heading', { name: 'Edit Running Shoes' })
    await fill('Price (USD)', '79.99')

    catalog.edit('RS-001', { stock: 99 })
    await grabbed.client?.invalidateQueries({ queryKey: ['products'] })
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(
      await screen.findByText(/changed by someone else since you opened it/),
    ).toBeInTheDocument()
    expect(catalog.requests.at(-1)).toMatchObject({ method: 'PUT', body: { version: 1 } })
    expect(catalog.bySku('RS-001')).toMatchObject({ stock: 99, price: '89.99', version: 2 })
  })

  it('shows a reload message on a version conflict, and Reload brings the latest version', async () => {
    asReviewer()
    const catalog = fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes', price: '89.99' }])
    renderApp('/admin/products')
    await user.click((await row('RS-001')).getByRole('link', { name: 'Edit' }))
    await screen.findByRole('heading', { name: 'Edit Running Shoes' })
    catalog.edit('RS-001', { name: 'Shoes Renamed Elsewhere' })

    await fill('Price (USD)', '79.99')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    const banner = await screen.findByText(/changed by someone else since you opened it/)
    expect(banner).toHaveTextContent('your unsaved changes will be lost')
    expect(notifications().queryByRole('alert')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Reload' }))

    expect(
      await screen.findByRole('heading', { name: 'Edit Shoes Renamed Elsewhere' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Price (USD)')).toHaveValue('89.99')
    expect(screen.queryByText(/changed by someone else/)).not.toBeInTheDocument()
  })

  it('keeps the values and shows the reference when the server fails', async () => {
    expectErrorNotifications()
    asReviewer()
    let posts = 0
    fakeCatalog()
    server.use(
      http.post(`${API}/products`, () => {
        posts += 1
        return serverError('req-save')
      }),
    )
    renderApp('/admin/products/new')
    await fillNewProduct(runningShoes)

    await user.click(screen.getByRole('button', { name: 'Create product' }))

    expect(await notifications().findByText('Reference: req-save')).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toHaveValue('Running Shoes')
    expect(screen.getByRole('button', { name: 'Create product' })).toBeEnabled()
    expect(posts).toBe(1)
  })

  it('sends one request when Save is clicked twice', async () => {
    expectErrorNotifications()
    asReviewer()
    let posts = 0
    fakeCatalog()
    server.use(
      http.post(`${API}/products`, async () => {
        posts += 1
        await delay(50)
        return serverError()
      }),
    )
    renderApp('/admin/products/new')
    await fillNewProduct(runningShoes)

    await user.dblClick(screen.getByRole('button', { name: 'Create product' }))

    await notifications().findByRole('alert')
    expect(posts).toBe(1)
  })

  it('says the product was not found for a bad link', async () => {
    asReviewer()
    fakeCatalog()
    renderApp('/admin/products/00000000-0000-4000-8000-999999999999/edit')

    expect(await screen.findByRole('heading', { name: 'Product not found' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to the products' })).toHaveAttribute(
      'href',
      '/admin/products',
    )
  })
})

describe('the owner test of 2026-11-21 (evidence in tasks/ECOM-007-evidence)', () => {
  it('creating a product, then a gift, then editing shows only success messages', async () => {
    asReviewer('Antonio')
    const catalog = fakeCatalog([
      { sku: 'RS-001', name: 'Running Shoes', category: 'Sports', price: '89.99' },
      { sku: 'GC-001', name: 'Small gift Shoes', category: 'Gifts', price: '0.00', gift: true },
    ])
    renderApp('/admin/products')

    await user.click(await screen.findByRole('link', { name: 'New product' }))
    await fillNewProduct({
      ...runningShoes,
      SKU: 'TS-002',
      Name: 'Trail Shoes',
      'Price (USD)': '120',
      Stock: '0',
    })
    await user.click(screen.getByRole('button', { name: 'Create product' }))
    await screen.findByRole('row', { name: 'TS-002' })

    await user.click(screen.getByRole('link', { name: 'New product' }))
    await fillNewProduct({
      ...runningShoes,
      SKU: 'GF-002',
      Name: 'Collar gift',
      'Price (USD)': '0',
    })
    await user.click(screen.getByRole('button', { name: 'Create product' }))
    await user.click(screen.getByRole('button', { name: 'Yes, mark as gift' }))
    await screen.findByRole('row', { name: 'GF-002' })

    await user.click((await row('RS-001')).getByRole('link', { name: 'Edit' }))
    await screen.findByRole('heading', { name: 'Edit Running Shoes' })
    await fill('Price (USD)', '79.99')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await (await row('RS-001')).findByText('$79.99')).toBeInTheDocument()

    await waitFor(() => expect(notifications().getAllByRole('status')).toHaveLength(3))
    expect(notifications().queryByRole('alert')).not.toBeInTheDocument()
    expect(catalog.requests.map((request) => request.method)).toEqual(['POST', 'POST', 'PUT'])
  })
})

describe('the history page', () => {
  it('lists every change oldest first, with the person, the time and the values', async () => {
    asReviewer('Maria')
    const catalog = fakeCatalog()
    renderApp('/admin/products/new')
    await fillNewProduct(runningShoes)
    await user.click(screen.getByRole('button', { name: 'Create product' }))
    const id = (await screen.findByRole('row', { name: 'RS-001' })) && catalog.bySku('RS-001')?.id
    catalog.edit('RS-001', { price: '79.99', stock: 3 })
    await user.click((await row('RS-001')).getByRole('button', { name: 'Archive' }))
    await user.click(
      within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Archive' }),
    )
    await waitFor(() => expect(catalog.bySku('RS-001')?.status).toBe('ARCHIVED'))

    await user.click(screen.getByRole('link', { name: 'Admin' }))
    renderApp(`/admin/products/${id}/history`)

    const timeline = within(await screen.findByRole('list', { name: 'Changes, oldest first' }))
    const entries = timeline.getAllByRole('listitem')
    expect(entries.map((entry) => entry.querySelector('strong')?.textContent)).toEqual([
      'Created',
      'Changed',
      'Archived',
    ])
    expect(entries[0]).toHaveTextContent('by Maria')
    expect(entries[0]).toHaveTextContent('Running Shoes')
    expect(entries[1]).toHaveTextContent('by Someone else')
    expect(entries[1]).toHaveTextContent('Price89.99 → 79.99')
    expect(entries[1]).toHaveTextContent('Stock10 → 3')
    expect(entries[2]).toHaveTextContent('StatusACTIVE → ARCHIVED')
    expect(entries[0].querySelector('time')).toHaveAttribute('dateTime')
  })

  it('says the product was not found', async () => {
    asReviewer()
    fakeCatalog()
    renderApp('/admin/products/00000000-0000-4000-8000-999999999999/history')

    expect(await screen.findByRole('heading', { name: 'Product not found' })).toBeInTheDocument()
  })
})
