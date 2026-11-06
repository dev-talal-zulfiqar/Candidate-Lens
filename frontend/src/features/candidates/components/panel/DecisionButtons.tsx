import type { CandidateDecision } from '../../../../types/candidate'
import { useUpdateDecisionMutation } from '../../hooks'

interface DecisionButtonsProps {
  jobId: string
  candidateId: string
  applicationId: string
  decision: CandidateDecision | null
}

const OPTIONS: { value: CandidateDecision; label: string; activeClass: string }[] = [
  { value: 'advance', label: 'Advance', activeClass: 'bg-emerald-600 text-white' },
  { value: 'hold', label: 'Hold', activeClass: 'bg-amber-600 text-white' },
  { value: 'decline', label: 'Decline', activeClass: 'bg-ink text-cream' },
]

export function DecisionButtons({
  jobId,
  candidateId,
  applicationId,
  decision,
}: DecisionButtonsProps) {
  const mutation = useUpdateDecisionMutation(jobId, candidateId)

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex gap-2">
        {OPTIONS.map((option) => {
          const isActive = decision === option.value
          return (
            <button
              key={option.value}
              type="button"
              disabled={mutation.isPending}
              onClick={() =>
                mutation.mutate({
                  applicationId,
                  decision: isActive ? null : option.value,
                })
              }
              className={`rounded-md border border-border-strong px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                isActive ? option.activeClass : 'bg-paper text-ink-600 hover:bg-cream-100'
              }`}
            >
              {option.label}
            </button>
          )
        })}
      </div>
      {mutation.isError && (
        <p role="alert" className="text-xs text-red-600">
          Couldn't save that decision — try again.
        </p>
      )}
    </div>
  )
}
