import type { JobRequirement } from '../../../types/job'

interface RequirementsListProps {
  requirements: JobRequirement[]
  onEdit?: () => void
}

export function RequirementsList({ requirements, onEdit }: RequirementsListProps) {
  const mandatory = requirements.filter((r) => r.category === 'mandatory')
  const preferred = requirements.filter((r) => r.category === 'preferred')

  return (
    <div className="flex flex-col gap-4">
      {onEdit && (
        <button type="button" onClick={onEdit} className="btn-secondary self-start">
          Edit requirements
        </button>
      )}
      <RequirementGroup title="Mandatory" requirements={mandatory} />
      <RequirementGroup title="Preferred" requirements={preferred} />
    </div>
  )
}

function RequirementGroup({
  title,
  requirements,
}: {
  title: string
  requirements: JobRequirement[]
}) {
  if (requirements.length === 0) return null

  return (
    <div>
      <h3 className="eyebrow mb-2">{title}</h3>
      <ul className="flex flex-col gap-2">
        {requirements.map((requirement) => (
          <li
            key={requirement.id}
            className="flex items-center justify-between gap-3 rounded-md border border-border bg-paper px-3 py-2 text-sm"
          >
            <span className="min-w-0 text-ink">{requirement.description}</span>
            <span className="pill bg-cream-100 text-ink-600">
              weight {requirement.weight}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
