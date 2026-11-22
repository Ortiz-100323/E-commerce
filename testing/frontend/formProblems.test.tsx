import { useMutation } from '@tanstack/react-query'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay } from 'msw'
import { http, HttpResponse } from 'msw/http'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { describe, expect, it } from 'vitest'

import { logInAs } from './support/fakeSession'
import type { FieldProblem } from '../../frontend/src/api/apiError'
import { productsApi, type NewProduct } from '../../frontend/src/api/products'
import { AppShell } from '../../frontend/src/app/AppShell'
import { AdminLayout } from '../../frontend/src/features/admin/AdminLayout'
import { applyProblemToForm } from '../../frontend/src/forms/applyProblemToForm'
import { FormProblems } from '../../frontend/src/forms/FormProblems'
import { TextField } from '../../frontend/src/forms/TextField'
import { API, product, validationProblem } from './support/api'
import { renderApp } from './support/renderApp'
import { server } from './support/server'

type Draft = { sku: string; name: string; price: string }
const FIELDS = ['sku', 'name', 'price'] as const

function ProbeForm() {
  const [problems, setProblems] = useState<FieldProblem[]>([])
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<Draft>({ defaultValues: { sku: 'GC-001', name: 'Gift Card', price: '0' } })
  const create = useMutation({
    mutationFn: (draft: Draft) => {
      const body: NewProduct = {
        ...draft,
        description: '',
        category: 'Gifts',
        stock: 1,
        weight_kg: '0',
        gift: false,
      }
      return productsApi.create(body)
    },
    onError: (error) => setProblems(applyProblemToForm(error, FIELDS, setError)),
  })
  return (
    <form
      onSubmit={handleSubmit((draft) => {
        setProblems([])
        create.mutate(draft)
      })}
    >
      <FormProblems problems={problems} />
      <TextField label="SKU" error={errors.sku} {...register('sku')} />
      <TextField label="Name" error={errors.name} {...register('name')} />
      <TextField label="Price" error={errors.price} {...register('price')} />
      <button type="submit" disabled={create.isPending}>
        Save
      </button>
      {create.isSuccess ? <p>Saved</p> : null}
    </form>
  )
}

const probeRoutes = [
  {
    element: <AppShell />,
    children: [
      {
        path: 'admin',
        element: <AdminLayout />,
        children: [{ path: 'probe', element: <ProbeForm /> }],
      },
    ],
  },
]

function renderProbe() {
  logInAs('ADMIN', 'Maria')
  return renderApp('/admin/probe', { routes: probeRoutes })
}

describe('API validation problems on forms', () => {
  it('marks each field named in the problem with its message', async () => {
    server.use(
      http.post(`${API}/products`, () =>
        validationProblem([
          {
            field: 'sku',
            code: 'invalid_sku_format',
            message: 'Use letters, digits and single hyphens only.',
          },
          {
            field: 'price',
            code: 'zero_price_requires_gift',
            message: 'A price of 0 must be confirmed as a gift.',
          },
        ]),
      ),
    )
    renderProbe()

    await userEvent.click(await screen.findByRole('button', { name: 'Save' }))

    const sku = await screen.findByLabelText('SKU')
    await waitFor(() => expect(sku).toHaveAttribute('aria-invalid', 'true'))
    expect(sku).toHaveAccessibleDescription('Use letters, digits and single hyphens only.')
    expect(screen.getByLabelText('Price')).toHaveAccessibleDescription(
      'A price of 0 must be confirmed as a gift.',
    )
    expect(screen.getByLabelText('Name')).not.toHaveAttribute('aria-invalid')
    expect(sku).toHaveFocus()
  })

  it('lists problems that match no field at the top of the form', async () => {
    server.use(
      http.post(`${API}/products`, () =>
        validationProblem([
          {
            location: 'query',
            field: 'dry_run',
            code: 'required',
            message: 'Field required',
          },
          {
            field: 'weight_kg',
            code: 'too_many_decimal_places',
            message: 'Use at most 3 decimal places.',
          },
          { field: 'name', code: 'markup_not_allowed', message: 'No HTML, please.' },
        ]),
      ),
    )
    renderProbe()

    await userEvent.click(await screen.findByRole('button', { name: 'Save' }))

    const list = await screen.findByText('Please fix the following:')
    const box = list.closest('[role="alert"]') as HTMLElement
    expect(within(box).getByText('dry_run: Field required')).toBeInTheDocument()
    expect(within(box).getByText('weight_kg: Use at most 3 decimal places.')).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toHaveAccessibleDescription('No HTML, please.')
  })

  it('does not raise a notification for a validation problem', async () => {
    server.use(
      http.post(`${API}/products`, () =>
        validationProblem([{ field: 'name', code: 'required', message: 'Tell us the name.' }]),
      ),
    )
    renderProbe()

    await userEvent.click(await screen.findByRole('button', { name: 'Save' }))

    await screen.findByText('Tell us the name.')
    const notifications = screen.getByRole('region', { name: 'Notifications' })
    expect(within(notifications).queryByRole('alert')).not.toBeInTheDocument()
  })

  it('sends one request when the button is clicked twice quickly', async () => {
    let requests = 0
    server.use(
      http.post(`${API}/products`, async () => {
        requests += 1
        await delay(50)
        return HttpResponse.json(product, { status: 201 })
      }),
    )
    renderProbe()
    const save = await screen.findByRole('button', { name: 'Save' })

    await userEvent.dblClick(save)

    expect(await screen.findByText('Saved')).toBeInTheDocument()
    expect(requests).toBe(1)
  })
})
