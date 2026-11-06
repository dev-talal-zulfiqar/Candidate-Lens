import { Link, useParams } from 'react-router'
import { useJobQuery } from '../jobs/hooks'
import { EvaluationPanel } from './components/panel/EvaluationPanel'
import { useCandidateBoardQuery } from './hooks'

export function CandidateApplicationPage() {
  const { jobId, applicationId } = useParams<{ jobId: string; applicationId: string }>()
  const jobQuery = useJobQuery(jobId ?? '')
  const boardQuery = useCandidateBoardQuery(jobId ?? '')

  if (!jobId || !applicationId) return null

  if (jobQuery.isLoading || boardQuery.isLoading) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="card h-48 animate-pulse" />
      </div>
    )
  }

  if (jobQuery.isError || !jobQuery.data || boardQuery.isError || !boardQuery.data) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-10">
        <p role="alert" className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          Couldn't load this candidate. Check that the backend is reachable
          and try again.
        </p>
        <Link to={`/jobs/${jobId}`} className="mt-4 inline-block text-sm text-ink-600 underline">
          ← Back to job
        </Link>
      </div>
    )
  }

  const selected = boardQuery.data.items.find((item) => item.application_id === applicationId)

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-10">
      <Link to={`/jobs/${jobId}`} className="eyebrow normal-case hover:text-ink-600">
        ← Back to {jobQuery.data.title}
      </Link>

      {selected ? (
        <EvaluationPanel
          jobId={jobId}
          selected={selected}
          isReviewing={selected.ai_evaluation === null}
        />
      ) : (
        <p role="alert" className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          Couldn't find this candidate on this job — they may have been
          removed.
        </p>
      )}
    </div>
  )
}
