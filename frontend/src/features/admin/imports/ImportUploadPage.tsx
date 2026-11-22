import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'

import { ApiError, type FieldProblem } from '../../../api/apiError'
import { FormProblems } from '../../../forms/FormProblems'
import styles from './Imports.module.css'
import { useUploadImport } from './queries'

function problemsOf(error: unknown): FieldProblem[] {
  if (!(error instanceof ApiError)) {
    return []
  }
  if (error.isValidation) {
    return error.errors
  }
  return [
    {
      location: 'body',
      field: '',
      code: error.problem,
      message: error.detail ?? error.title,
      params: {},
    },
  ]
}

export function ImportUploadPage() {
  const upload = useUploadImport()
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (file === null) {
      return
    }
    upload.mutate(file, {
      onSuccess: (batch) => navigate(`/admin/imports/${batch.id}`),
    })
  }

  return (
    <section aria-labelledby="upload-title">
      <h2 id="upload-title">Import products from a CSV file</h2>
      <p>
        The file is checked first. Nothing reaches the catalog until you review the flagged rows and
        press <strong>Commit import</strong>.
      </p>
      <form className={styles.upload} onSubmit={submit}>
        <label>
          CSV file
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => {
              upload.reset()
              setFile(event.target.files?.[0] ?? null)
            }}
          />
        </label>
        <FormProblems problems={problemsOf(upload.error)} />
        <button
          type="submit"
          className={styles.primary}
          disabled={file === null || upload.isPending}
        >
          {upload.isPending ? 'Checking…' : 'Upload and check'}
        </button>
      </form>
    </section>
  )
}
