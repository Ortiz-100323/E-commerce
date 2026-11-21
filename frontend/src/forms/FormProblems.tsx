import type { FieldProblem } from '../api/apiError'
import styles from './Forms.module.css'

const LABELS: Record<string, string> = {
  'X-Actor-Name': 'Reviewer name',
}

function label(problem: FieldProblem): string {
  return LABELS[problem.field] ?? problem.field
}

export function FormProblems({ problems }: { problems: FieldProblem[] }) {
  if (problems.length === 0) {
    return null
  }
  return (
    <div role="alert" className={styles.problems}>
      <p>Please fix the following:</p>
      <ul>
        {problems.map((problem) => (
          <li key={`${problem.location}:${problem.field}:${problem.code}`}>
            {problem.field ? `${label(problem)}: ` : ''}
            {problem.message}
          </li>
        ))}
      </ul>
    </div>
  )
}
