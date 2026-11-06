import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { CandidateBoardTable } from '../candidates/components/CandidateBoardTable'
import { ReviewingBanner } from '../candidates/components/ReviewingBanner'
import { useCandidateBoardQuery } from '../candidates/hooks'
import { useEvaluationQueue } from '../candidates/useEvaluationQueue'
import { useToast } from '../../components/useToast'
import { ResumeUploadForm } from '../resumes/components/ResumeUploadForm'
import type { UploadBatch } from '../../types/upload'
import { MarkdownPreview } from './components/MarkdownPreview'
import { RequirementsEditor } from './components/RequirementsEditor'
import { RequirementsList } from './components/RequirementsList'
import { useDeleteJobMutation, useJobQuery, useRerunEvaluationsMutation } from './hooks'

function ChevronIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
      className="h-3.5 w-3.5 shrink-0 text-ink-400 transition-transform group-open:rotate-90"
    >
      <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const jobQuery = useJobQuery(jobId ?? '')

  if (!jobId) return null

  if (jobQuery.isLoading) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="card h-32 animate-pulse" />
      </div>
    )
  }

  if (jobQuery.isError || !jobQuery.data) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-10">
        <p role="alert" className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          Couldn't load this job. It may not exist, or the backend may be
          unreachable.
        </p>
        <Link to="/" className="mt-4 inline-block text-sm text-ink-600 underline">
          Back to jobs
        </Link>
      </div>
    )
  }

  return <JobDetailContent job={jobQuery.data} />
}

function JobDetailContent({ job }: { job: NonNullable<ReturnType<typeof useJobQuery>['data']> }) {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [editingRequirements, setEditingRequirements] = useState(false)
  const hasConfirmedRequirements = job.requirements.length > 0

  const boardQuery = useCandidateBoardQuery(job.id, hasConfirmedRequirements)
  const items = boardQuery.data?.items ?? []
  const queue = useEvaluationQueue(job.id, items, hasConfirmedRequirements)
  const deleteJobMutation = useDeleteJobMutation()
  const rerunMutation = useRerunEvaluationsMutation(job.id)

  useEffect(() => {
    if (queue.creditsExhausted) {
      showToast('Out of AI credits! Please contact admin.')
    }
  }, [queue.creditsExhausted, showToast])

  const handleDelete = async () => {
    const confirmed = window.confirm(
      `Delete "${job.title}"? This removes all of its candidates, uploads, and evaluations. This can't be undone.`,
    )
    if (!confirmed) return
    try {
      await deleteJobMutation.mutateAsync(job.id)
      navigate('/')
    } catch {
      // Already surfaced via deleteJobMutation.isError below — this only
      // stops the rejection from becoming an unhandled promise rejection.
    }
  }

  const handleUploaded = (response: UploadBatch) => {
    const failed = response.results.filter((result) => result.status === 'failed')
    if (failed.length === 0) return
    const reasons = failed
      .map((result) => `${result.filename}${result.error ? ` (${result.error})` : ''}`)
      .join(', ')
    showToast(
      `${failed.length} ${failed.length === 1 ? 'resume' : 'resumes'} could not be processed: ${reasons}`,
    )
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8 px-6 py-10">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link to="/" className="eyebrow normal-case hover:text-ink-600">
            ← All jobs
          </Link>
          <p className="eyebrow mt-4">Pipeline</p>
          <h1 className="mt-1 text-4xl text-ink">{job.title}</h1>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={() => rerunMutation.mutate()}
            disabled={
              rerunMutation.isPending
              || !hasConfirmedRequirements
              || items.length === 0
              || queue.pendingCount > 0
            }
            className="btn-secondary"
          >
            {rerunMutation.isPending ? 'Re-evaluating…' : 'Re-evaluate'}
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleteJobMutation.isPending}
            className="rounded-md border border-red-200 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {deleteJobMutation.isPending ? 'Deleting…' : 'Delete pipeline'}
          </button>
        </div>
      </div>
      {deleteJobMutation.isError && (
        <p role="alert" className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          {deleteJobMutation.error.message}
        </p>
      )}
      {rerunMutation.isError && (
        <p role="alert" className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          {rerunMutation.error.message}
        </p>
      )}

      <details className="card group p-5">
        <summary className="eyebrow flex cursor-pointer list-none items-center gap-2 normal-case">
          <ChevronIcon />
          Job description
        </summary>
        <div className="mt-4">
          <MarkdownPreview markdown={job.description_md} />
        </div>
      </details>

      <details
        className="card group p-5"
        open={!hasConfirmedRequirements || editingRequirements}
      >
        <summary className="eyebrow flex cursor-pointer list-none items-center gap-2 normal-case">
          <ChevronIcon />
          {hasConfirmedRequirements
            ? `Requirements · ${job.requirements.length} confirmed`
            : 'Requirements · set up before uploading resumes'}
        </summary>
        <div className="mt-4">
          {hasConfirmedRequirements ? (
            editingRequirements ? (
              <RequirementsEditor
                jobId={job.id}
                existing={job.requirements}
                onCancel={() => setEditingRequirements(false)}
                onSaved={() => setEditingRequirements(false)}
              />
            ) : (
              <RequirementsList
                requirements={job.requirements}
                onEdit={() => setEditingRequirements(true)}
              />
            )
          ) : (
            <RequirementsEditor jobId={job.id} />
          )}
        </div>
      </details>

      <ResumeUploadForm jobId={job.id} onUploaded={handleUploaded} />

      <ReviewingBanner pendingCount={queue.pendingCount} onRestart={queue.restart} />

      {boardQuery.isLoading && <div className="card h-48 animate-pulse" />}

      {boardQuery.isError && (
        <p role="alert" className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          Couldn't load candidates. Check that the backend is reachable and
          try again.
        </p>
      )}

      {boardQuery.data && (
        <CandidateBoardTable
          jobId={job.id}
          items={items}
          hasAnyCandidates={boardQuery.data.summary.total_applications > 0}
          reviewingIds={queue.reviewingIds}
          erroredIds={queue.erroredIds}
          onRetry={queue.restart}
        />
      )}
    </div>
  )
}
