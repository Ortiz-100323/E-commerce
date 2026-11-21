import { http, HttpResponse } from 'msw/http'

import type { HistoryEntry, Product } from '../../../frontend/src/api/products'
import { API, problem, validationProblem } from './api'
import { server } from './server'

type Draft = {
  sku?: string
  name: string
  description: string
  category: string
  price: string
  stock: number
  weight_kg: string
  gift: boolean
  version?: number
}

type Recorded = { method: string; path: string; actor: string | null; body: unknown }

const FIELDS = ['name', 'description', 'category', 'price', 'stock', 'weight_kg', 'tags', 'status']

let counter = 0
let clock = Date.UTC(2026, 10, 21, 10, 0, 0)

function nextId(): string {
  counter += 1
  return `00000000-0000-4000-8000-${String(counter).padStart(12, '0')}`
}

function now(): string {
  clock += 60_000
  return new Date(clock).toISOString()
}

function money(value: string): string {
  return Number(value).toFixed(2)
}

function weight(value: string): string {
  return Number(value).toFixed(3)
}

function snapshot(product: Product): Record<string, unknown> {
  return {
    sku: product.sku,
    name: product.name,
    description: product.description,
    category: product.category,
    price: product.price,
    stock: product.stock,
    weight_kg: product.weight_kg,
    tags: product.tags,
    status: product.status,
  }
}

function validate(draft: Draft) {
  const errors = []
  if (draft.name.includes('<')) {
    errors.push({
      field: 'name',
      code: 'markup_not_allowed',
      message: 'Remove < and > from the name.',
    })
  }
  if (Number(draft.price) === 0 && !draft.gift) {
    errors.push({
      field: 'price',
      code: 'zero_price_requires_gift',
      message: 'A price of 0 must be confirmed as a gift.',
    })
  }
  if (Number(draft.price) !== 0 && draft.gift) {
    errors.push({
      field: 'price',
      code: 'gift_must_be_free',
      message: 'A gift must be free. Set the price to 0, or untick the gift.',
    })
  }
  return errors.length > 0 ? validationProblem(errors) : null
}

export function fakeCatalog(seed: Partial<Product>[] = []) {
  const products = new Map<string, Product>()
  const history = new Map<string, HistoryEntry[]>()
  const requests: Recorded[] = []

  const log = (product: Product, event: string, actor: string, before: unknown, after: unknown) => {
    const entries = history.get(product.id) ?? []
    entries.push({
      event,
      occurred_at: product.updated_at,
      actor,
      sku: product.sku,
      before: before as Record<string, unknown> | null,
      after: after as Record<string, unknown> | null,
      context: {},
    })
    history.set(product.id, entries)
  }

  const record = async (request: Request): Promise<{ actor: string; body: unknown }> => {
    const raw = request.headers.get('X-Actor-Name')
    const body =
      request.method === 'POST' || request.method === 'PUT'
        ? await request
            .clone()
            .json()
            .catch(() => null)
        : null
    requests.push({ method: request.method, path: new URL(request.url).pathname, actor: raw, body })
    return { actor: raw === null ? '' : decodeURIComponent(raw), body }
  }

  const store = (draft: Draft, actor: string): Product => {
    const at = now()
    const product: Product = {
      id: nextId(),
      sku: (draft.sku ?? '').toUpperCase(),
      name: draft.name,
      description: draft.description,
      category: draft.category,
      price: money(draft.price),
      currency: 'USD',
      stock: draft.stock,
      weight_kg: weight(draft.weight_kg),
      gift: draft.gift,
      tags: draft.gift ? ['GIFT'] : [],
      status: 'ACTIVE',
      is_sellable: draft.stock > 0,
      version: 1,
      created_at: at,
      updated_at: at,
    }
    products.set(product.id, product)
    log(product, 'product.created', actor, null, snapshot(product))
    return product
  }

  const change = (current: Product, next: Product, actor: string): Product => {
    const before = snapshot(current)
    const after = snapshot(next)
    const changed = FIELDS.filter(
      (field) => JSON.stringify(before[field]) !== JSON.stringify(after[field]),
    )
    if (changed.length === 0) {
      return current
    }
    const updated = {
      ...next,
      version: current.version + 1,
      updated_at: now(),
      is_sellable: next.status === 'ACTIVE' && next.stock > 0,
    }
    products.set(updated.id, updated)
    const event =
      changed.length === 1 && changed[0] === 'status'
        ? next.status === 'ARCHIVED'
          ? 'product.archived'
          : 'product.restored'
        : 'product.changed'
    log(
      updated,
      event,
      actor,
      Object.fromEntries(changed.map((field) => [field, before[field]])),
      Object.fromEntries(changed.map((field) => [field, after[field]])),
    )
    return updated
  }

  for (const partial of seed) {
    const product = store(
      {
        sku: partial.sku ?? `SKU-${counter + 1}`,
        name: partial.name ?? 'Product',
        description: partial.description ?? '',
        category: partial.category ?? 'General',
        price: partial.price ?? '10.00',
        stock: partial.stock ?? 5,
        weight_kg: partial.weight_kg ?? '1.000',
        gift: partial.gift ?? false,
      },
      'Seed',
    )
    if (partial.status === 'ARCHIVED') {
      change(product, { ...product, status: 'ARCHIVED' }, 'Seed')
    }
  }

  const notFound = () =>
    problem({
      status: 404,
      slug: 'not-found',
      title: 'The resource was not found.',
      detail: 'Product not found.',
    })

  server.use(
    http.get(`${API}/products`, ({ request }) => {
      const url = new URL(request.url)
      const q = (url.searchParams.get('q') ?? '').toLowerCase()
      const status = url.searchParams.get('status') ?? 'ACTIVE'
      const page = Number(url.searchParams.get('page') ?? '1')
      const size = Number(url.searchParams.get('page_size') ?? '20')
      const matching = [...products.values()]
        .filter((product) => status === 'ALL' || product.status === status)
        .filter((product) =>
          [product.name, product.sku, product.description].some((text) =>
            text.toLowerCase().includes(q),
          ),
        )
        .sort((left, right) => left.name.toLowerCase().localeCompare(right.name.toLowerCase()))
      return HttpResponse.json({
        items: matching.slice((page - 1) * size, page * size),
        total: matching.length,
        page,
        page_size: size,
      })
    }),
    http.get(`${API}/categories`, () =>
      HttpResponse.json({
        items: [
          ...new Set(
            [...products.values()].filter((p) => p.status === 'ACTIVE').map((p) => p.category),
          ),
        ].sort(),
      }),
    ),
    http.get(`${API}/products/:id`, ({ params }) => {
      const product = products.get(String(params.id))
      return product ? HttpResponse.json(product) : notFound()
    }),
    http.get(`${API}/products/:id/history`, ({ params }) => {
      const id = String(params.id)
      return products.has(id)
        ? HttpResponse.json({ product_id: id, entries: history.get(id) ?? [] })
        : notFound()
    }),
    http.post(`${API}/products`, async ({ request }) => {
      const { actor, body } = await record(request)
      const draft = body as Draft
      const invalid = validate(draft)
      if (invalid) {
        return invalid
      }
      const sku = (draft.sku ?? '').toUpperCase()
      if ([...products.values()].some((product) => product.sku === sku)) {
        return problem({
          status: 409,
          slug: 'duplicate-sku',
          title: 'This SKU is already taken.',
          detail: `SKU ${sku} is already taken.`,
          extra: { sku },
        })
      }
      return HttpResponse.json(store(draft, actor), { status: 201 })
    }),
    http.put(`${API}/products/:id`, async ({ request, params }) => {
      const { actor, body } = await record(request)
      const current = products.get(String(params.id))
      if (!current) {
        return notFound()
      }
      const draft = body as Draft
      const invalid = validate(draft)
      if (invalid) {
        return invalid
      }
      const next: Product = {
        ...current,
        name: draft.name,
        description: draft.description,
        category: draft.category,
        price: money(draft.price),
        stock: draft.stock,
        weight_kg: weight(draft.weight_kg),
        gift: draft.gift,
        tags: draft.gift ? ['GIFT'] : [],
      }
      if (draft.version !== current.version) {
        return problem({
          status: 409,
          slug: 'version-conflict',
          title: 'The product was changed by someone else. Reload it and try again.',
          detail: `You edited version ${draft.version}, but the product is now at version ${current.version}.`,
          extra: { current_version: current.version },
        })
      }
      return HttpResponse.json(change(current, next, actor))
    }),
    http.delete(`${API}/products/:id`, async ({ request, params }) => {
      const { actor } = await record(request)
      const current = products.get(String(params.id))
      return current
        ? HttpResponse.json(change(current, { ...current, status: 'ARCHIVED' }, actor))
        : notFound()
    }),
    http.post(`${API}/products/:id/restore`, async ({ request, params }) => {
      const { actor } = await record(request)
      const current = products.get(String(params.id))
      return current
        ? HttpResponse.json(change(current, { ...current, status: 'ACTIVE' }, actor))
        : notFound()
    }),
  )

  return {
    products,
    history,
    requests,
    bySku: (sku: string) => [...products.values()].find((product) => product.sku === sku),
    edit: (sku: string, changes: Partial<Product>) => {
      const current = [...products.values()].find((product) => product.sku === sku)
      if (!current) {
        throw new Error(`No product ${sku}`)
      }
      return change(current, { ...current, ...changes }, 'Someone else')
    },
  }
}
