import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { importsApi, type ImportBatch, type Resolve, type RowChange } from '../../../api/imports'
import { productKeys } from '../../../api/productQueries'
import type { MutationMeta } from '../../../app/queryClient'

export const importKeys = {
  all: ['imports'] as const,
  detail: (id: string) => ['imports', 'detail', id] as const,
}

export const COMMIT_PROBLEMS = [
  'import-not-committable',
  'import-stale-rows',
  'import-not-pending',
  'not-found',
]
export const RESOLVE_PROBLEMS = ['import-row-not-resolvable', 'import-not-pending', 'not-found']
export const UPLOAD_PROBLEMS = ['payload-too-large', 'unsupported-media-type']

export function useImport(id: string) {
  return useQuery({
    queryKey: importKeys.detail(id),
    queryFn: () => importsApi.get(id),
    meta: { handledProblems: ['not-found'] },
  })
}

export function useUploadImport() {
  const client = useQueryClient()
  const meta: MutationMeta = { handledProblems: UPLOAD_PROBLEMS }
  return useMutation({
    mutationFn: (file: File) => importsApi.upload(file),
    onSuccess: (batch) => client.setQueryData(importKeys.detail(batch.id), batch),
    meta,
  })
}

export function mergeRowChange(batch: ImportBatch | undefined, change: RowChange) {
  if (batch === undefined) {
    return batch
  }
  return {
    ...batch,
    ...change.batch,
    items: batch.items.map((row) => (row.line === change.row.line ? change.row : row)),
  }
}

export function useResolveRow(id: string) {
  const client = useQueryClient()
  const meta: MutationMeta = { handledProblems: RESOLVE_PROBLEMS }
  return useMutation({
    mutationFn: ({ line, resolve }: { line: number; resolve: Resolve }) =>
      importsApi.resolve(id, line, resolve),
    onSuccess: (change) =>
      client.setQueryData<ImportBatch>(importKeys.detail(id), (batch) =>
        mergeRowChange(batch, change),
      ),
    meta,
  })
}

function useFinish(id: string, action: (id: string) => Promise<ImportBatch>) {
  const client = useQueryClient()
  const meta: MutationMeta = { handledProblems: COMMIT_PROBLEMS }
  return useMutation({
    mutationFn: () => action(id),
    onSuccess: async (batch) => {
      client.setQueryData(importKeys.detail(id), batch)
      await client.invalidateQueries({ queryKey: productKeys.lists, refetchType: 'all' })
    },
    onError: async () => {
      await client.invalidateQueries({ queryKey: importKeys.detail(id) })
    },
    meta,
  })
}

export function useCommitImport(id: string) {
  return useFinish(id, importsApi.commit)
}

export function useDiscardImport(id: string) {
  return useFinish(id, importsApi.discard)
}
