import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import { useCategories, useProductList } from '../../api/productQueries'
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

function SearchBox({
  search,
  onApply,
}: {
  search: ShopSearch
  onApply: (filters: TextFilters) => void
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
    }
  }

  return (
    <form role="search" onSubmit={submit} className={styles.searchBox} noValidate>
      <label className={styles.grow}>
        Search
        <input
          type="search"
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder="What are you looking for?"
        />
      </label>
      <div className={styles.priceField}>
        <label htmlFor="min-price">Min price</label>
        <input
          id="min-price"
          inputMode="decimal"
          value={minPrice}
          onChange={(event) => setMinPrice(event.target.value)}
          aria-invalid={errors.minPrice ? true : undefined}
          aria-describedby={errors.minPrice ? 'min-price-error' : undefined}
        />
        {errors.minPrice ? (
          <span id="min-price-error" className={styles.fieldError}>
            {errors.minPrice}
          </span>
        ) : null}
      </div>
      <div className={styles.priceField}>
        <label htmlFor="max-price">Max price</label>
        <input
          id="max-price"
          inputMode="decimal"
          value={maxPrice}
          onChange={(event) => setMaxPrice(event.target.value)}
          aria-invalid={errors.maxPrice ? true : undefined}
          aria-describedby={errors.maxPrice ? 'max-price-error' : undefined}
        />
        {errors.maxPrice ? (
          <span id="max-price-error" className={styles.fieldError}>
            {errors.maxPrice}
          </span>
        ) : null}
      </div>
      <button type="submit">Search</button>
    </form>
  )
}

export function StorefrontPage() {
  const [params, setParams] = useSearchParams()
  const search = parseShopSearch(params)
  const list = useProductList(toProductQuery(search))
  const categories = useCategories()

  const apply = (changes: Partial<ShopSearch>) =>
    setParams(toSearchParams({ ...search, page: 1, ...changes }))

  const data = list.data
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <section aria-labelledby="shop-title">
      <h1 id="shop-title">Shop</h1>
      <SearchBox key={params.toString()} search={search} onApply={apply} />
      <div className={styles.filters}>
        <label>
          Category
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
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={search.inStock}
            onChange={(event) => apply({ inStock: event.target.checked })}
          />
          In stock only
        </label>
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={search.giftsOnly}
            onChange={(event) => apply({ giftsOnly: event.target.checked })}
          />
          Gifts only
        </label>
        <label>
          Sort by
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

      {list.isPending ? <p>Loading products…</p> : null}
      {list.isError && !data ? (
        <p>
          We couldn't load the products.{' '}
          <button type="button" onClick={() => void list.refetch()}>
            Try again
          </button>
        </p>
      ) : null}

      {data && data.total === 0 ? (
        <p>
          No products match your search.{' '}
          {hasFilters(search) ? <Link to="/">Clear filters</Link> : null}
        </p>
      ) : null}

      {data && data.items.length > 0 ? (
        <>
          <p className={styles.summary}>
            {data.total} {data.total === 1 ? 'product' : 'products'}
          </p>
          <ul className={styles.grid} aria-label="Products">
            {data.items.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </ul>
        </>
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
          <span>
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
