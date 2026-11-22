import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'

import { useCategories, useProductList } from '../../api/productQueries'
import type { Product } from '../../api/products'
import controls from '../../styles/controls.module.css'
import { ProductCard } from './ProductCard'
import {
  hasFilters,
  isPrice,
  parseShopSearch,
  SORT_OPTIONS,
  toProductQuery,
  toSearchParams,
  type ShopSearch,
} from './shopSearch'
import styles from './Storefront.module.css'

type TextFilters = Pick<ShopSearch, 'q' | 'minPrice' | 'maxPrice'>

function priceErrors(
  minPrice: string,
  maxPrice: string,
): Partial<Record<'minPrice' | 'maxPrice', string>> {
  const errors: Partial<Record<'minPrice' | 'maxPrice', string>> = {}
  if (minPrice.trim() !== '' && !isPrice(minPrice)) {
    errors.minPrice = 'Use a price like 19.99.'
  }
  if (maxPrice.trim() !== '' && !isPrice(maxPrice)) {
    errors.maxPrice = 'Use a price like 19.99.'
  }
  if (
    !errors.minPrice &&
    !errors.maxPrice &&
    minPrice.trim() !== '' &&
    maxPrice.trim() !== '' &&
    Number(minPrice) > Number(maxPrice)
  ) {
    errors.maxPrice = 'The minimum price must not be above the maximum.'
  }
  return errors
}

function SearchIcon({ className }: { className: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4 4" />
    </svg>
  )
}

function PriceInput({
  id,
  label,
  placeholder,
  value,
  error,
  onChange,
}: {
  id: string
  label: string
  placeholder: string
  value: string
  error: string | undefined
  onChange: (value: string) => void
}) {
  return (
    <div className={styles.priceField}>
      <label htmlFor={id} className={controls.visuallyHidden}>
        {label}
      </label>
      <input
        id={id}
        inputMode="decimal"
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
      />
      {error ? (
        <span id={`${id}-error`} className={styles.fieldError}>
          {error}
        </span>
      ) : null}
    </div>
  )
}

function SearchPanel({
  search,
  onApply,
  open,
  onOpenChange,
  active,
  children,
}: {
  search: ShopSearch
  onApply: (filters: TextFilters) => void
  open: boolean
  onOpenChange: (open: boolean) => void
  active: number
  children: ReactNode
}) {
  const [q, setQ] = useState(search.q)
  const [minPrice, setMinPrice] = useState(search.minPrice)
  const [maxPrice, setMaxPrice] = useState(search.maxPrice)
  const [errors, setErrors] = useState<ReturnType<typeof priceErrors>>({})

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const found = priceErrors(minPrice, maxPrice)
    setErrors(found)
    if (Object.keys(found).length === 0) {
      onApply({ q: q.trim(), minPrice: minPrice.trim(), maxPrice: maxPrice.trim() })
    } else {
      onOpenChange(true)
    }
  }

  return (
    <form role="search" onSubmit={submit} className={styles.panel} noValidate>
      <div className={styles.searchRow}>
        <label className={styles.searchField}>
          <span className={controls.visuallyHidden}>Search</span>
          <SearchIcon className={styles.searchIcon} />
          <input
            type="search"
            value={q}
            onChange={(event) => setQ(event.target.value)}
            placeholder="What are you looking for?"
          />
        </label>
        <button type="submit" className={controls.primary}>
          Search
        </button>
      </div>
      <button
        type="button"
        className={styles.filtersToggle}
        aria-expanded={open}
        aria-controls="shop-filters"
        onClick={() => onOpenChange(!open)}
      >
        {active > 0 ? `Filters (${active})` : 'Filters'}
      </button>
      <div id="shop-filters" className={styles.filterRow} data-open={open || undefined}>
        {children}
        <div role="group" aria-labelledby="price-label" className={styles.control}>
          <span id="price-label" className={styles.label}>
            Price
          </span>
          <div className={styles.priceRange}>
            <PriceInput
              id="min-price"
              label="Min price"
              placeholder="Min"
              value={minPrice}
              error={errors.minPrice}
              onChange={setMinPrice}
            />
            <span className={styles.dash} aria-hidden="true">
              –
            </span>
            <PriceInput
              id="max-price"
              label="Max price"
              placeholder="Max"
              value={maxPrice}
              error={errors.maxPrice}
              onChange={setMaxPrice}
            />
          </div>
        </div>
      </div>
    </form>
  )
}

function lookAlikes(products: Product[]): Set<string> {
  const seen = new Map<string, number>()
  for (const product of products) {
    const key = product.name.trim().toLowerCase()
    seen.set(key, (seen.get(key) ?? 0) + 1)
  }
  return new Set([...seen].filter(([, total]) => total > 1).map(([name]) => name))
}

function EmptyResults({ filtered }: { filtered: boolean }) {
  return (
    <div className={styles.empty}>
      <SearchIcon className={styles.emptyIcon} />
      <h2 className={styles.emptyTitle}>No products match your search</h2>
      <p className={styles.emptyText}>Try another word, a wider price range, or fewer filters.</p>
      {filtered ? (
        <Link to="/" className={controls.secondary}>
          Clear filters
        </Link>
      ) : null}
    </div>
  )
}

export function StorefrontPage() {
  const [params, setParams] = useSearchParams()
  const search = parseShopSearch(params)
  const list = useProductList(toProductQuery(search))
  const categories = useCategories()
  const [filtersOpen, setFiltersOpen] = useState(false)
  const activeFilters = [
    search.category !== '',
    search.inStock,
    search.giftsOnly,
    search.minPrice !== '' || search.maxPrice !== '',
  ].filter(Boolean).length

  const apply = (changes: Partial<ShopSearch>) =>
    setParams(toSearchParams({ ...search, page: 1, ...changes }))

  const data = list.data
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const twins = lookAlikes(data?.items ?? [])

  useEffect(() => {
    if (data && !list.isPlaceholderData && search.page > pages) {
      setParams(toSearchParams({ ...search, page: pages }), { replace: true })
    }
  }, [data, list.isPlaceholderData, pages, search, setParams])

  return (
    <section aria-labelledby="shop-title">
      <h1 id="shop-title">Shop</h1>
      <SearchPanel
        key={params.toString()}
        search={search}
        onApply={apply}
        open={filtersOpen}
        onOpenChange={setFiltersOpen}
        active={activeFilters}
      >
        <label className={styles.control}>
          <span className={styles.label}>Category</span>
          <select
            value={search.category}
            onChange={(event) => apply({ category: event.target.value })}
          >
            <option value="">All categories</option>
            {(categories.data?.items ?? []).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <div className={styles.toggles}>
          <label className={styles.toggle}>
            <input
              type="checkbox"
              checked={search.inStock}
              onChange={(event) => apply({ inStock: event.target.checked })}
            />
            In stock only
          </label>
          <label className={styles.toggle}>
            <input
              type="checkbox"
              checked={search.giftsOnly}
              onChange={(event) => apply({ giftsOnly: event.target.checked })}
            />
            Gifts only
          </label>
        </div>
      </SearchPanel>

      <div className={styles.resultsBar}>
        <p className={styles.summary} aria-live="polite">
          {list.isPending ? 'Loading products…' : null}
          {data ? `${data.total} ${data.total === 1 ? 'product' : 'products'}` : null}
        </p>
        <label className={styles.sort}>
          <span className={styles.sortLabel}>Sort by</span>
          <select
            value={search.sort}
            onChange={(event) =>
              apply({
                sort: SORT_OPTIONS.find((option) => option.value === event.target.value)?.value,
              })
            }
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {list.isError && !data ? (
        <div className={`${controls.alert} ${styles.loadError}`}>
          <p>We couldn't load the products.</p>
          <button type="button" className={controls.secondary} onClick={() => void list.refetch()}>
            Try again
          </button>
        </div>
      ) : null}

      {data && data.total === 0 ? <EmptyResults filtered={hasFilters(search)} /> : null}

      {data && data.items.length > 0 ? (
        <ul className={styles.grid} aria-label="Products">
          {data.items.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              showSku={twins.has(product.name.trim().toLowerCase())}
            />
          ))}
        </ul>
      ) : null}

      {data && data.total > data.page_size ? (
        <nav aria-label="Pages" className={styles.pager}>
          <button
            type="button"
            disabled={search.page <= 1}
            onClick={() => setParams(toSearchParams({ ...search, page: search.page - 1 }))}
          >
            Previous
          </button>
          <span className={styles.pageOf}>
            Page {search.page} of {pages}
          </span>
          <button
            type="button"
            disabled={search.page >= pages}
            onClick={() => setParams(toSearchParams({ ...search, page: search.page + 1 }))}
          >
            Next
          </button>
        </nav>
      ) : null}
    </section>
  )
}
