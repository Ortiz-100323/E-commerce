import { screen, waitFor, within } from '@testing-library/react'
import userEvent, { type UserEvent } from '@testing-library/user-event'
import { http } from 'msw/http'
import { beforeEach, describe, expect, it } from 'vitest'

import { ACTOR_STORAGE_KEY } from '../../frontend/src/actor/actorStorage'
import { API, problem } from './support/api'
import {
  fakeImports,
  IMPORT_ID,
  importRow,
  reviewRow,
  sampleRows,
  updateRow,
} from './support/fakeImports'
import { renderApp } from './support/renderApp'
import { server } from './support/server'

const REVIEW = `/admin/imports/${IMPORT_ID}`
const CSV =
  'name,sku,description,category,price,stock,weight_kg\r\nYoga Mat,YM-015,,Sports,free,200,1.2'

let user: UserEvent

beforeEach(() => {
  user = userEvent.setup()
  window.localStorage.setItem(ACTOR_STORAGE_KEY, 'Maria')
})

function tab(name: RegExp) {
  return screen.getByRole('tab', { name })
}

async function openTab(name: RegExp) {
  await user.click(await screen.findByRole('tab', { name }))
  return within(screen.getByRole('tabpanel'))
}

async function card(line: number) {
  return within(await screen.findByRole('article', { name: `Line ${line}` }))
}

function commitButton() {
  return screen.getByRole('button', { name: 'Commit import' })
}

async function chooseFile(content: string, name = 'products.csv', type = 'text/csv') {
  const input = await screen.findByLabelText('CSV file')
  await user.upload(input, new File([content], name, { type }))
}

describe('uploading a CSV file', () => {
  it('sends the file as the body and shows the expected count on every tab', async () => {
    const fake = fakeImports()
    const { router } = renderApp('/admin/imports/new')

    await chooseFile(CSV)
    await user.click(screen.getByRole('button', { name: 'Upload and check' }))

    await screen.findByRole('heading', { name: 'Review import: products.csv' })
    expect(router.state.location.pathname).toBe(REVIEW)
    expect(fake.uploads).toEqual([
      { contentType: 'text/csv', actor: 'Maria', fileName: 'products.csv', body: CSV },
    ])
    expect(screen.getAllByRole('tab').map((item) => item.textContent)).toEqual([
      'Needs review (6)',
      'Updates (0)',
      'New (84)',
      'Unchanged (0)',
      'Skipped (0)',
      'Rejected (2)',
      'Superseded (3)',
      'Blank (2)',
      'Warnings (3)',
    ])
    expect(tab(/Needs review/)).toHaveAttribute('aria-selected', 'true')
    expect(screen.getAllByRole('article')).toHaveLength(6)
  })

  it('explains a file that cannot be read and stays on the page', async () => {
    fakeImports()
    renderApp('/admin/imports/new')

    await chooseFile('sku,name\r\nA-1,Thing')
    await user.click(screen.getByRole('button', { name: 'Upload and check' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(
      'File: These columns are missing: description, category, price, stock, weight_kg.',
    )
    expect(screen.getByRole('heading', { name: 'Import products from a CSV file' })).toBeVisible()
  })

  it('explains a file that is too large without a pop-up notification', async () => {
    server.use(
      http.post(`${API}/imports`, () =>
        problem({
          status: 413,
          slug: 'payload-too-large',
          title: 'The upload is too large.',
          detail: 'The file is larger than 5242880 bytes.',
        }),
      ),
    )
    renderApp('/admin/imports/new')

    await chooseFile(CSV)
    await user.click(screen.getByRole('button', { name: 'Upload and check' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The file is larger than 5242880 bytes.',
    )
  })

  it('lets the server reject a selected file whose media type is not CSV', async () => {
    let contentType: string | null = null
    server.use(
      http.post(`${API}/imports`, ({ request }) => {
        contentType = request.headers.get('Content-Type')
        return problem({
          status: 415,
          slug: 'unsupported-media-type',
          title: 'The file type is not supported.',
          detail: 'Upload a .csv file (text/csv).',
        })
      }),
    )
    renderApp('/admin/imports/new')

    await chooseFile(CSV, 'products.csv', 'text/plain')
    await user.click(screen.getByRole('button', { name: 'Upload and check' }))

    expect(contentType).toBe('text/plain')
    expect(await screen.findByRole('alert')).toHaveTextContent('Upload a .csv file (text/csv).')
  })

  it('keeps the button disabled until a file is chosen', async () => {
    renderApp('/admin/imports/new')

    expect(await screen.findByRole('button', { name: 'Upload and check' })).toBeDisabled()
  })
})

describe('reviewing the rows held for review', () => {
  it('moves a corrected row to the right tab and updates the counts', async () => {
    const fake = fakeImports()
    renderApp(REVIEW)

    const keyboard = await card(50)
    await user.type(keyboard.getByLabelText('Weight (kg)'), '1.10')
    await user.click(keyboard.getByRole('button', { name: 'Save correction' }))

    await waitFor(() => expect(tab(/Needs review/)).toHaveTextContent('Needs review (5)'))
    expect(tab(/^New/)).toHaveTextContent('New (85)')
    expect(screen.queryByRole('article', { name: 'Line 50' })).not.toBeInTheDocument()
    expect(fake.resolutions).toEqual([
      { line: 50, actor: 'Maria', body: { action: 'correct', values: { weight_kg: '1.10' } } },
    ])
    const created = await openTab(/^New/)
    expect(created.getByRole('row', { name: 'Line 50' })).toHaveTextContent('Reviewed')
  })

  it('keeps a correction that still needs review in the review tab', async () => {
    fakeImports()
    renderApp(REVIEW)

    const box = await card(52)
    await user.type(box.getByLabelText('Category'), 'Gifts')
    await user.clear(box.getByLabelText('Price'))
    await user.type(box.getByLabelText('Price'), '0')
    await user.click(box.getByRole('button', { name: 'Save correction' }))

    const again = await card(52)
    expect(await again.findByRole('button', { name: 'Confirm as free gift' })).toBeVisible()
    expect(tab(/Needs review/)).toHaveTextContent('Needs review (6)')
  })

  it('shows the field errors of an invalid correction and keeps the row', async () => {
    fakeImports()
    renderApp(REVIEW)

    const mat = await card(7)
    await user.clear(mat.getByLabelText('Price'))
    await user.type(mat.getByLabelText('Price'), 'abc')
    await user.click(mat.getByRole('button', { name: 'Save correction' }))

    expect(await mat.findByRole('alert')).toHaveTextContent(
      'Price: The price is not a number like 19.99.',
    )
    expect(tab(/Needs review/)).toHaveTextContent('Needs review (6)')
  })

  it('confirms a zero price as a free gift and skips a row', async () => {
    const fake = fakeImports()
    renderApp(REVIEW)

    await user.click((await card(7)).getByRole('button', { name: 'Confirm as free gift' }))
    await waitFor(() => expect(tab(/Needs review/)).toHaveTextContent('Needs review (5)'))
    await user.click((await card(25)).getByRole('button', { name: 'Skip this row' }))

    await waitFor(() => expect(tab(/Needs review/)).toHaveTextContent('Needs review (4)'))
    expect(tab(/Skipped/)).toHaveTextContent('Skipped (1)')
    expect(screen.queryByRole('article', { name: 'Line 25' })).not.toBeInTheDocument()
    expect(fake.resolutions.map((item) => item.body)).toEqual([
      { action: 'confirm', expected_outcome: 'needs_review' },
      { action: 'skip' },
    ])
    expect(screen.getByText('Waiting for a decision on lines 41, 47, 50, 52.')).toBeVisible()
    const skipped = await openTab(/Skipped/)
    expect(skipped.getByText(/These rows will not be imported/)).toBeVisible()
    const headphones = within(skipped.getByRole('article', { name: 'Line 25' }))
    expect(headphones.getByText(/Skipped/)).toBeVisible()
    expect(headphones.queryByRole('button', { name: 'Skip this row' })).toBeNull()
  })

  it('brings a skipped row back by correcting it on the skipped tab', async () => {
    fakeImports()
    renderApp(REVIEW)
    await user.click((await card(25)).getByRole('button', { name: 'Skip this row' }))
    await waitFor(() => expect(tab(/Skipped/)).toHaveTextContent('Skipped (1)'))

    const skipped = await openTab(/Skipped/)
    const headphones = within(skipped.getByRole('article', { name: 'Line 25' }))
    await user.type(headphones.getByLabelText('Name'), 'Headphones')
    await user.click(headphones.getByRole('button', { name: 'Save correction' }))

    await waitFor(() => expect(tab(/Skipped/)).toHaveTextContent('Skipped (0)'))
    expect(tab(/Needs review/)).toHaveTextContent('Needs review (5)')
    expect(tab(/^New/)).toHaveTextContent('New (85)')
    expect(screen.getByRole('tabpanel')).toHaveTextContent('No rows here.')
  })

  it('offers no confirm button for an empty value', async () => {
    fakeImports()
    renderApp(REVIEW)

    const headphones = await card(25)
    expect(headphones.queryByRole('button', { name: /Confirm/ })).toBeNull()
    expect(headphones.getByRole('button', { name: 'Save correction' })).toBeDisabled()
  })
})

describe('reviewing comfortably', () => {
  it('keeps the Import CSV tab marked while an import is reviewed', async () => {
    fakeImports(sampleRows())
    renderApp(REVIEW)

    const nav = within(await screen.findByRole('navigation', { name: 'Admin' }))

    expect(nav.getByRole('link', { name: 'Import CSV' })).toHaveAttribute('aria-current', 'page')
    expect(nav.getByRole('link', { name: 'Products' })).not.toHaveAttribute('aria-current')
  })

  it('gives long descriptions a text area', async () => {
    fakeImports(sampleRows())
    renderApp(REVIEW)

    const description = (await card(7)).getByLabelText('Description')

    expect(description.tagName).toBe('TEXTAREA')
  })

  it('shows the spaces in the raw line, so an empty-looking name explains itself', async () => {
    fakeImports(sampleRows())
    renderApp(REVIEW)

    const line = await card(41)

    expect(line.getByText(/······/)).toBeVisible()
    expect(line.getByText('· marks a space.')).toBeVisible()
  })

  it('moves focus to the next row to review after a decision', async () => {
    fakeImports(sampleRows())
    renderApp(REVIEW)
    const panel = await openTab(/Needs review/)
    const [first, second] = panel.getAllByRole('article')
    const next = second.getAttribute('aria-label') ?? ''

    await user.click(within(first).getByRole('button', { name: 'Skip this row' }))

    await waitFor(() => expect(screen.getByRole('article', { name: next })).toHaveFocus())
  })
})

describe('committing', () => {
  it('enables commit only when nothing is left to resolve, then shows the result', async () => {
    fakeImports([
      importRow(2, 'create'),
      reviewRow(3, 'zero_price', 'price', { price: '0' }),
      reviewRow(4, 'empty_required_field', 'category', { category: '' }),
    ])
    renderApp(REVIEW)

    await card(3)
    expect(commitButton()).toBeDisabled()
    expect(screen.getByText('Waiting for a decision on lines 3, 4.')).toBeVisible()
    await user.click((await card(3)).getByRole('button', { name: 'Confirm as free gift' }))
    await waitFor(() => expect(commitButton()).toBeDisabled())
    const empty = await card(4)
    await user.type(empty.getByLabelText('Category'), 'Sports')
    await user.click(empty.getByRole('button', { name: 'Save correction' }))
    await waitFor(() => expect(commitButton()).toBeEnabled())
    await user.click(commitButton())

    const status = await screen.findByRole('status')
    expect(status).toHaveTextContent('Imported. 3 created, 0 updated, 0 skipped.')
    expect(within(status).getByRole('link', { name: 'See the products' })).toHaveAttribute(
      'href',
      '/admin/products',
    )
    expect(screen.queryByRole('button', { name: 'Commit import' })).toBeNull()
  })

  it('explains stale rows and shows them again with the latest changes', async () => {
    const fake = fakeImports([updateRow(2, 'RS-001')])
    renderApp(REVIEW)
    await user.click(await screen.findByRole('checkbox', { name: /Confirm this update/ }))
    await waitFor(() => expect(commitButton()).toBeEnabled())
    fake.failNextCommit(
      problem({
        status: 409,
        slug: 'import-stale-rows',
        title: 'Some products changed after the file was checked.',
        detail: 'The products on lines 2 changed after the file was checked.',
        extra: { lines: [2] },
      }),
    )
    fake.changeRow(2, {
      decision: null,
      changes: { price: { before: '91.00', after: '94.99' } },
    })

    await user.click(commitButton())

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Some products changed after the file was checked.')
    expect(alert).toHaveTextContent('Nothing was imported. The rows on lines 2 now show')
    expect(await screen.findByText('91.00')).toBeVisible()
    expect(screen.getByRole('checkbox', { name: /Confirm this update/ })).not.toBeChecked()
    expect(commitButton()).toBeDisabled()
  })

  it('explains a commit refused because rows are pending', async () => {
    const fake = fakeImports([importRow(2, 'create')])
    renderApp(REVIEW)
    await waitFor(() => expect(commitButton()).toBeEnabled())
    fake.failNextCommit(
      problem({
        status: 409,
        slug: 'import-not-committable',
        title: 'Some rows still need a decision before the import.',
        detail: 'Resolve or skip these lines first: 2.',
        extra: { pending_lines: [2] },
      }),
    )

    await user.click(commitButton())

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Resolve or skip these lines first: 2.',
    )
  })

  it('discards the import after a confirmation', async () => {
    fakeImports()
    renderApp(REVIEW)

    await user.click(await screen.findByRole('button', { name: 'Discard import' }))
    const dialog = within(screen.getByRole('alertdialog', { name: 'Discard this import?' }))
    await user.click(dialog.getByRole('button', { name: 'Discard import' }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      'This import was discarded. Nothing was imported.',
    )
    expect(screen.queryByRole('button', { name: 'Commit import' })).toBeNull()
  })
})

describe('the other tabs', () => {
  it('confirms one update with its checkbox and the rest with confirm all', async () => {
    const fake = fakeImports([
      updateRow(2, 'RS-001'),
      updateRow(3, 'RS-002'),
      updateRow(4, 'RS-003'),
    ])
    renderApp(REVIEW)

    const shoes = await card(2)
    expect(shoes.getByRole('row', { name: /Price/ })).toHaveTextContent('Price89.9994.99')
    await user.click(shoes.getByRole('checkbox', { name: /Confirm this update/ }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Confirm all 2 updates' })).toBeVisible(),
    )
    await user.click(screen.getByRole('button', { name: 'Confirm all 2 updates' }))

    await waitFor(() => expect(commitButton()).toBeEnabled())
    expect(fake.resolutions.map((item) => item.line)).toEqual([2, 3, 4])
    expect(screen.queryByRole('button', { name: /Confirm all/ })).toBeNull()
  })

  it('moves an update to the skipped tab when its checkbox is cleared, and back', async () => {
    const fake = fakeImports([updateRow(2, 'RS-001')])
    renderApp(REVIEW)
    const checkbox = () => screen.getByRole('checkbox', { name: /Confirm this update/ })
    await user.click(await screen.findByRole('checkbox', { name: /Confirm this update/ }))
    await waitFor(() => expect(checkbox()).toBeChecked())

    await user.click(checkbox())

    await waitFor(() => expect(tab(/Updates/)).toHaveTextContent('Updates (0)'))
    expect(tab(/Skipped/)).toHaveTextContent('Skipped (1)')
    expect(screen.getByRole('tabpanel')).toHaveTextContent('No rows here.')
    const skipped = await openTab(/Skipped/)
    const shoes = within(skipped.getByRole('article', { name: 'Line 2' }))
    expect(shoes.getByText(/Skipped/)).toBeVisible()
    await user.click(shoes.getByRole('checkbox', { name: /Confirm this update/ }))

    await waitFor(() => expect(tab(/Updates/)).toHaveTextContent('Updates (1)'))
    expect(tab(/Skipped/)).toHaveTextContent('Skipped (0)')
    expect(fake.resolutions.map((item) => item.body.action)).toEqual(['confirm', 'skip', 'confirm'])
  })

  it('shows skipped rows read-only after the import is committed', async () => {
    const fake = fakeImports(sampleRows())
    fake.changeRow(41, { decision: 'skipped', pending: false })
    fake.batch.status = 'COMMITTED'
    renderApp(REVIEW)

    await waitFor(() => expect(tab(/Skipped/)).toHaveTextContent('Skipped (1)'))
    const skipped = await openTab(/Skipped/)
    expect(skipped.getByRole('row', { name: 'Line 41' })).toHaveTextContent('Skipped')
    expect(skipped.queryByRole('textbox')).toBeNull()
    expect(skipped.queryByRole('button', { name: 'Save correction' })).toBeNull()
  })

  it('shows a finished import as a short read-only summary', async () => {
    const fake = fakeImports(sampleRows())
    fake.batch.status = 'COMMITTED'
    renderApp(REVIEW)

    const panel = await openTab(/Needs review/)

    expect(panel.queryByRole('article')).toBeNull()
    expect(panel.queryByRole('textbox')).toBeNull()
    expect(panel.getByRole('row', { name: 'Line 7' })).toBeInTheDocument()
  })

  it('lists rejected rows with their reasons and raw line, and cannot edit them', async () => {
    fakeImports()
    renderApp(REVIEW)

    const panel = await openTab(/Rejected/)

    const script = panel.getByRole('row', { name: 'Line 20' })
    expect(script).toHaveTextContent('Name: The name cannot contain < or >.')
    expect(script).toHaveTextContent("<script>alert('xss')</script>")
    expect(panel.queryByRole('textbox')).toBeNull()
    expect(panel.getByText(/Fix them in the source file/)).toBeVisible()
  })

  it('shows superseded rows, blank lines and warnings', async () => {
    fakeImports()
    renderApp(REVIEW)

    const superseded = await openTab(/Superseded/)
    expect(superseded.getByRole('row', { name: 'Line 2' })).toHaveTextContent(
      'Line 36, later in the file',
    )
    const blank = await openTab(/Blank/)
    expect(blank.getByText('Empty lines, ignored: 62, 63.')).toBeVisible()
    const warnings = await openTab(/Warnings/)
    expect(warnings.getAllByRole('row')).toHaveLength(4)
    expect(warnings.getByText('The $ was removed; stored 29.99.')).toBeVisible()
  })

  it('opens on the updates tab when nothing needs review', async () => {
    fakeImports([importRow(2, 'create'), updateRow(3, 'RS-001')])
    renderApp(REVIEW)

    await waitFor(() => expect(tab(/Updates/)).toHaveAttribute('aria-selected', 'true'))
    const empty = await openTab(/Unchanged/)
    expect(empty.getByText('No rows here.')).toBeVisible()
  })
})

describe('an import that cannot be used', () => {
  it('says when an import does not exist', async () => {
    fakeImports()
    renderApp('/admin/imports/00000000-0000-4000-8000-000000000999')

    expect(await screen.findByRole('alert')).toHaveTextContent('This import was not found.')
  })

  it('shows an expired import without the commit button', async () => {
    const fake = fakeImports(sampleRows())
    fake.batch.status = 'EXPIRED'
    renderApp(REVIEW)

    expect(await screen.findByRole('status')).toHaveTextContent(
      'This import expired 24 hours after the upload.',
    )
    expect(screen.queryByRole('button', { name: 'Commit import' })).toBeNull()
    const panel = within(screen.getByRole('tabpanel'))
    expect(panel.getByRole('row', { name: 'Line 7' })).toBeInTheDocument()
    expect(panel.queryByRole('button', { name: 'Save correction' })).toBeNull()
  })

  it('is reachable from the admin navigation', async () => {
    renderApp('/admin/products')

    await user.click(await screen.findByRole('link', { name: 'Import CSV' }))

    expect(
      await screen.findByRole('heading', { name: 'Import products from a CSV file' }),
    ).toBeVisible()
  })
})
