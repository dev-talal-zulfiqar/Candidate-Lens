import { Link } from 'react-router'
import type { CandidateDecision, CandidatePoolEntry } from '../../../types/candidate'
import { useDeleteApplicationMutation } from '../hooks'

function ViewScoreIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
      className="h-4 w-4"
    >
      <path
        d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M15 3h6v6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M10 14 21 3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
      className="h-4 w-4"
    >
      <path d="M3 6h18" strokeLinecap="round" />
      <path
        d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M10 11v6M14 11v6" strokeLinecap="round" />
    </svg>
  )
}

const DECISION_STYLES: Record<CandidateDecision, string> = {
  advance: 'bg-emerald-100 text-emerald-800',
  hold: 'bg-amber-100 text-amber-800',
  decline: 'bg-ink-400/15 text-ink-600',
}

const DECISION_LABELS: Record<CandidateDecision, string> = {
  advance: 'Advance',
  hold: 'Hold',
  decline: 'Decline',
}

interface CandidateBoardTableProps {
  jobId: string
  items: CandidatePoolEntry[]
  hasAnyCandidates: boolean
  reviewingIds: Set<string>
  erroredIds: Set<string>
  onRetry: () => void
}

export function CandidateBoardTable({
  jobId,
  items,
  hasAnyCandidates,
  reviewingIds,
  erroredIds,
  onRetry,
}: CandidateBoardTableProps) {
  if (items.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border-strong px-3 py-10 text-center text-sm text-ink-400">
        {hasAnyCandidates ? 'No candidates match the current view.' : 'No candidates yet.'}
      </p>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-paper">
      <table className="w-full text-left text-sm">
        <thead className="eyebrow border-b border-border">
          <tr>
            <th className="px-4 py-2.5 font-mono">#</th>
            <th className="px-4 py-2.5 font-mono">Candidate</th>
            <th className="px-4 py-2.5 font-mono">Score</th>
            <th className="px-4 py-2.5 font-mono">Baseline</th>
            <th className="px-4 py-2.5 font-mono">Decision</th>
            <th className="px-4 py-2.5 font-mono">Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <CandidateRow
              key={item.application_id}
              jobId={jobId}
              index={index + 1}
              item={item}
              isReviewing={reviewingIds.has(item.application_id)}
              isErrored={erroredIds.has(item.application_id)}
              onRetry={onRetry}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CandidateRow({
  jobId,
  index,
  item,
  isReviewing,
  isErrored,
  onRetry,
}: {
  jobId: string
  index: number
  item: CandidatePoolEntry
  isReviewing: boolean
  isErrored: boolean
  onRetry: () => void
}) {
  const deleteMutation = useDeleteApplicationMutation(jobId)

  const handleDelete = () => {
    const confirmed = window.confirm(
      `Remove ${item.resume_filename} from this pipeline? This can't be undone.`,
    )
    if (!confirmed) return
    deleteMutation.mutate(item.application_id)
  }

  return (
    <tr className="border-b border-border last:border-0">
      <td className="px-4 py-3 font-mono text-ink-400">{index}</td>
      <td className="px-4 py-3">
        <span className="font-display text-base break-words text-ink">
          {item.resume_filename}
        </span>
      </td>
      <td className="px-4 py-3">
        <ScoreCell item={item} isReviewing={isReviewing} isErrored={isErrored} onRetry={onRetry} />
      </td>
      <td className="px-4 py-3 font-mono text-ink-600">
        {item.baseline ? `${item.baseline.met}/${item.baseline.total}` : '—'}
      </td>
      <td className="px-4 py-3">
        {item.decision ? (
          <span className={`pill ${DECISION_STYLES[item.decision]}`}>
            {DECISION_LABELS[item.decision]}
          </span>
        ) : (
          <span className="text-ink-400">—</span>
        )}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          {item.ai_evaluation ? (
            <Link
              to={`/jobs/${jobId}/candidates/${item.application_id}`}
              aria-label="View score"
              title="View score"
              className="rounded-md p-1.5 text-terracotta transition-colors hover:bg-terracotta-50"
            >
              <ViewScoreIcon />
            </Link>
          ) : (
            <span
              aria-label="Score not ready yet"
              title="Score not ready yet"
              className="rounded-md p-1.5 text-ink-400/40"
            >
              <ViewScoreIcon />
            </span>
          )}
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            aria-label="Delete resume"
            title="Delete resume"
            className="rounded-md p-1.5 text-red-700 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <TrashIcon />
          </button>
        </div>
        {deleteMutation.isError && (
          <p role="alert" className="mt-1 text-xs text-red-600">
            {deleteMutation.error.message}
          </p>
        )}
      </td>
    </tr>
  )
}

function ScoreCell({
  item,
  isReviewing,
  isErrored,
  onRetry,
}: {
  item: CandidatePoolEntry
  isReviewing: boolean
  isErrored: boolean
  onRetry: () => void
}) {
  if (item.extraction_status === 'failed') {
    return <span className="text-xs text-ink-400">Couldn't read resume</span>
  }
  if (item.ai_evaluation) {
    return (
      <span className="font-mono text-ink">
        {Math.round(Number(item.ai_evaluation.score))}
        <span className="text-ink-400"> /100</span>
      </span>
    )
  }
  if (isReviewing) {
    return <span className="text-ink-400 italic">Reviewing…</span>
  }
  if (isErrored) {
    return (
      <button type="button" onClick={onRetry} className="text-xs text-red-700 underline">
        Couldn't evaluate · Retry
      </button>
    )
  }
  return <span className="text-xs text-ink-400">Not yet evaluated</span>
}
