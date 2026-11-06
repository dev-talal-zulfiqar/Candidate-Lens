import type { Strength } from '../../../../types/evaluation'

function SparkleIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className="mt-0.5 h-4 w-4 shrink-0 text-terracotta"
    >
      <path d="M12 2l1.8 5.4L19 9l-5.2 1.6L12 16l-1.8-5.4L5 9l5.2-1.6L12 2zM5 17l.9 2.6L8.5 20l-2.6.9L5 23.5l-.9-2.6L1.5 20l2.6-.9L5 17zm14-2l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2z" />
    </svg>
  )
}

interface StandoutsListProps {
  strengths: Strength[]
}

export function StandoutsList({ strengths }: StandoutsListProps) {
  if (strengths.length === 0) {
    return <p className="text-sm text-ink-400">No noteworthy strengths identified.</p>
  }

  return (
    <ul className="flex flex-col gap-3">
      {strengths.map((strength, index) => (
        <li key={index} className="flex gap-2">
          <SparkleIcon />
          <div>
            <p className="text-sm font-semibold text-ink">{strength.description}</p>
            <p className="mt-0.5 text-xs text-ink-600 italic">
              "{strength.evidence_quote}"
            </p>
          </div>
        </li>
      ))}
    </ul>
  )
}
