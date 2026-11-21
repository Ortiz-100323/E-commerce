import { request } from './client'

export type ProductStatus = 'ACTIVE' | 'ARCHIVED'

export type Product = {
  id: string
  sku: string
  name: string
  description: string
  category: string
  price: string
  currency: string
  stock: number
  weight_kg: string
  gift: boolean
  tags: string[]
  status: ProductStatus
  is_sellable: boolean
  version: number
  created_at: string
  updated_at: string
}

export type ProductFields = {
  name: string
  description: string
  category: string
  price: string
  stock: number
  weight_kg: string
  gift: boolean
}

export type NewProduct = ProductFields & { sku: string }

export type ProductUpdate = ProductFields & { version: number }

export type ProductSort = 'name' | '-name' | 'price' | '-price' | 'created_at' | '-created_at'

export type ProductQuery = {
  q?: string
  category?: string
  min_price?: string
  max_price?: string
  in_stock?: boolean
  tag?: 'GIFT'
  status?: ProductStatus | 'ALL'
  sort?: ProductSort
  page?: number
  page_size?: number
}

export type ProductPage = {
  items: Product[]
  total: number
  page: number
  page_size: number
}

export type HistoryEntry = {
  event: string
  occurred_at: string
  actor: string
  sku: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  context: Record<string, unknown>
}

export type ProductHistory = {
  product_id: string
  entries: HistoryEntry[]
}

const path = (id: string, suffix = '') => `/products/${encodeURIComponent(id)}${suffix}`

export const productsApi = {
  search: (query: ProductQuery = {}) => request<ProductPage>('GET', '/products', { query }),
  get: (id: string) => request<Product>('GET', path(id)),
  history: (id: string) => request<ProductHistory>('GET', path(id, '/history')),
  categories: () => request<{ items: string[] }>('GET', '/categories'),
  create: (product: NewProduct, actor: string) =>
    request<Product>('POST', '/products', { body: product, actor }),
  update: (id: string, update: ProductUpdate, actor: string) =>
    request<Product>('PUT', path(id), { body: update, actor }),
  archive: (id: string, actor: string) => request<Product>('DELETE', path(id), { actor }),
  restore: (id: string, actor: string) => request<Product>('POST', path(id, '/restore'), { actor }),
}
