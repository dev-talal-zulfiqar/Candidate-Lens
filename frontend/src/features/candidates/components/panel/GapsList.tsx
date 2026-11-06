function WarningIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className="mt-0.5 h-4 w-4 shrink-0 text-amber-600"
    >
      <path d="M12 3L2 20h20L12 3zm0 5.5l5.6 9.7H6.4L12 8.5zM11 11v4h2v-4h-2zm0 5v2h2v-2h-2z" />
    </svg>
  )
}

interface GapsListProps {
  questions: string[]
}

export function GapsList({ questions }: GapsListProps) {
  if (questions.length === 0) {
    return <p className="text-sm text-ink-400">No follow-up questions identified.</p>
  }

  return (
    <ul className="flex flex-col gap-3">
      {questions.map((question, index) => (
        <li key={index} className="flex gap-2">
          <WarningIcon />
          <p className="text-sm text-ink">{question}</p>
        </li>
      ))}
    </ul>
  )
}
