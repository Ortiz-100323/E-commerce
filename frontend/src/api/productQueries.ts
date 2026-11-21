import { useQuery } from '@tanstack/react-query'

import type { MutationMeta } from '../app/queryClient'
import { productsApi, type ProductQuery } from './products'

export const productKeys = {
  all: ['products'] as const,
  lists: ['products', 'list'] as const,
  list: (query: ProductQuery) => ['products', 'list', query] as const,
  detail: (id: string) => ['products', 'detail', id] as const,
  history: (id: string) => ['products', 'history', id] as const,
  categories: ['categories'] as const,
}

const pageMeta: MutationMeta = { handledProblems: ['not-found'] }

export function useProductList(query: ProductQuery, enabled = true) {
  return useQuery({
    queryKey: productKeys.list(query),
    queryFn: () => productsApi.search(query),
    placeholderData: (previous) => previous,
    enabled,
  })
}

export function useProduct(id: string) {
  return useQuery({
    queryKey: productKeys.detail(id),
    queryFn: () => productsApi.get(id),
    meta: pageMeta,
  })
}

export function useProductHistory(id: string) {
  return useQuery({
    queryKey: productKeys.history(id),
    queryFn: () => productsApi.history(id),
    meta: pageMeta,
  })
}

export function useCategories() {
  return useQuery({ queryKey: productKeys.categories, queryFn: () => productsApi.categories() })
}
