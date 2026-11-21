import type { FieldPath, FieldValues, UseFormSetError } from 'react-hook-form'

import { ApiError, type FieldProblem } from '../api/apiError'

export function applyProblemToForm<T extends FieldValues>(
  error: unknown,
  fields: readonly FieldPath<T>[],
  setError: UseFormSetError<T>,
): FieldProblem[] {
  if (!(error instanceof ApiError) || !error.isValidation) {
    return []
  }
  const known = new Set<string>(fields)
  const unmatched: FieldProblem[] = []
  let focused = false
  for (const problem of error.errors) {
    if (problem.location === 'body' && known.has(problem.field)) {
      setError(
        problem.field as FieldPath<T>,
        { type: problem.code, message: problem.message },
        { shouldFocus: !focused },
      )
      focused = true
    } else {
      unmatched.push(problem)
    }
  }
  return unmatched
}
