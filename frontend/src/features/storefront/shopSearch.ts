import type { ProductQuery, ProductSort } from '../../api/products'

export const SHOP_PAGE_SIZE = 12

export const SORT_OPTIONS: { value: ProductSort; label: string }[] = [
  { value: 'name', label: 'Name A–Z' },
  { value: '-name', label: 'Name Z–A' },
  { value: 'price', label: 'Price: low to high' },
  { value: '-price', label: 'Price: high to low' },
  { value: '-created_at', label: 'Newest' },
]

const PRICE = /^\d+(\.\d{1,2})?$/

export type ShopSearch = {
  q: string
  category: string
  minPrice: string
  maxPrice: string
  inStock: boolean
  giftsOnly: boolean
  sort: ProductSort
  page: number
}

export const DEFAULT_SEARCH: ShopSearch = {
  q: '',
  category: '',
  minPrice: '',
  maxPrice: '',
  inStock: false,
  giftsOnly: false,
  sort: 'name',
  page: 1,
}

export function isPrice(value: string): boolean {
  return PRICE.test(value.trim())
}

function sortOf(raw: string | null): ProductSort {
  return SORT_OPTIONS.find((option) => option.value === raw)?.value ?? DEFAULT_SEARCH.sort
}

function pageOf(raw: string | null): number {
  const page = Number(raw)
  return Number.isInteger(page) && page >= 1 ? page : 1
}

function priceOf(raw: string | null): string {
  return raw !== null && isPrice(raw) ? raw.trim() : ''
}

export function parseShopSearch(params: URLSearchParams): ShopSearch {
  const minPrice = priceOf(params.get('min_price'))
  const maxPrice = priceOf(params.get('max_price'))
  const inverted = minPrice !== '' && maxPrice !== '' && Number(minPrice) > Number(maxPrice)
  return {
    q: (params.get('q') ?? '').trim(),
    category: (params.get('category') ?? '').trim(),
    minPrice: inverted ? '' : minPrice,
    maxPrice: inverted ? '' : maxPrice,
    inStock: params.get('in_stock') === 'true',
    giftsOnly: params.get('tag') === 'GIFT',
    sort: sortOf(params.get('sort')),
    page: pageOf(params.get('page')),
  }
}

export function toSearchParams(search: ShopSearch): URLSearchParams {
  const params = new URLSearchParams()
  const set = (key: string, value: string, fallback: string) => {
    if (value !== fallback) {
      params.set(key, value)
    }
  }
  set('q', search.q, '')
  set('category', search.category, '')
  set('min_price', search.minPrice, '')
  set('max_price', search.maxPrice, '')
  set('in_stock', search.inStock ? 'true' : '', '')
  set('tag', search.giftsOnly ? 'GIFT' : '', '')
  set('sort', search.sort, DEFAULT_SEARCH.sort)
  set('page', String(search.page), '1')
  return params
}

export function toProductQuery(search: ShopSearch): ProductQuery {
  return {
    q: search.q || undefined,
    category: search.category || undefined,
    min_price: search.minPrice || undefined,
    max_price: search.maxPrice || undefined,
    in_stock: search.inStock ? true : undefined,
    tag: search.giftsOnly ? 'GIFT' : undefined,
    status: 'ACTIVE',
    sort: search.sort,
    page: search.page,
    page_size: SHOP_PAGE_SIZE,
  }
}

export function hasFilters(search: ShopSearch): boolean {
  return toSearchParams({ ...search, sort: DEFAULT_SEARCH.sort, page: 1 }).toString() !== ''
}
