import type { RequirementResult } from '../../../../types/evaluation'

const STATUS_STYLES: Record<RequirementResult['status'], string> = {
  met: 'bg-emerald-100 text-emerald-800',
  not_met: 'bg-amber-100 text-amber-800',
  unverified: 'bg-ink-400/15 text-ink-600',
}

// "not_met" is softened to "Partial" rather than a hard negative — the AI
// never decides who gets hired, so a gap is a prompt to verify, not a
// rejection, matching the "not disqualifiers" framing used throughout this
// panel.
const STATUS_LABELS: Record<RequirementResult['status'], string> = {
  met: 'Met',
  not_met: 'Partial',
  unverified: 'Unclear',
}

function QuoteIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-400"
    >
      <path d="M9.5 7C6.5 7 4 9.5 4 12.5V18h5.5v-5.5H7c0-2 1.5-3.5 3.5-3.5V7h-1zm9 0c-3 0-5.5 2.5-5.5 5.5V18H18.5v-5.5H16c0-2 1.5-3.5 3.5-3.5V7h-1z" />
    </svg>
  )
}

interface RequirementEvidenceListProps {
  title: string
  results: RequirementResult[]
}

export function RequirementEvidenceList({ title, results }: RequirementEvidenceListProps) {
  if (results.length === 0) return null

  return (
    <div>
      <h3 className="eyebrow mb-2">{title}</h3>
      <ul className="flex flex-col gap-2">
        {results.map((result) => (
          <li key={result.id} className="rounded-md border border-border bg-paper p-3">
            <div className="flex items-start justify-between gap-3">
              <span className="text-sm text-ink">{result.requirement_description}</span>
              <span className={`pill shrink-0 ${STATUS_STYLES[result.status]}`}>
                {STATUS_LABELS[result.status]}
              </span>
            </div>
            {result.evidence_json.length > 0 && (
              <ul className="mt-2 flex flex-col gap-1">
                {result.evidence_json.slice(0, 2).map((evidence, index) => (
                  <li key={index} className="flex items-start gap-1.5 text-xs text-ink-600 italic">
                    <QuoteIcon />
                    <span>"{evidence.quote ?? evidence.term}"</span>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
