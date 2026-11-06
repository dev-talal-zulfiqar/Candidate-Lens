import type { ReactNode } from 'react'
import { API_BASE_URL } from '../../../../api/client'
import type { CandidatePoolEntry } from '../../../../types/candidate'
import type { ApplicationDetail } from '../../../../types/candidateDetail'
import type { Evaluation } from '../../../../types/evaluation'
import { useCandidateDetailQuery, useTriggerAIEvaluationForCandidateMutation } from '../../hooks'
import { DecisionButtons } from './DecisionButtons'
import { FitGauge } from './FitGauge'
import { fitQualityLabel } from './fitQuality'
import { GapsList } from './GapsList'
import { RequirementEvidenceList } from './RequirementEvidenceList'
import { StandoutsList } from './StandoutsList'

interface EvaluationPanelProps {
  jobId: string
  selected: CandidatePoolEntry | null
  isReviewing: boolean
}

export function EvaluationPanel({ jobId, selected, isReviewing }: EvaluationPanelProps) {
  if (!selected) {
    return (
      <div className="card flex h-full min-h-[20rem] min-w-0 items-center justify-center p-6 text-center text-sm text-ink-400">
        Select a reviewed candidate to see the full evaluation.
      </div>
    )
  }

  if (selected.extraction_status === 'failed') {
    return (
      <PanelShell>
        <p className="text-sm text-ink-600">
          This resume couldn't be read, so there's nothing to evaluate yet.
        </p>
      </PanelShell>
    )
  }

  if (isReviewing) {
    return <ReviewingState jobId={jobId} selected={selected} />
  }

  return <LoadedPanel key={selected.application_id} jobId={jobId} selected={selected} />
}

function PanelShell({ children }: { children: ReactNode }) {
  return <div className="card flex min-h-[20rem] min-w-0 flex-col gap-4 p-6">{children}</div>
}

/** Shown while the complete AI evaluation isn't ready yet. Always paired
 * with a manual recovery action: there's no polling on this page, so
 * without it a hung/never-triggered evaluation would otherwise leave the
 * user stuck here indefinitely (QA-007). Also surfaces the preliminary
 * pre-screen result on its own terms — never implying it's the final,
 * complete evaluation — since that distinction must hold everywhere this
 * candidate's standing is shown, not just on the board.
 */
function ReviewingState({ jobId, selected }: { jobId: string; selected: CandidatePoolEntry }) {
  const triggerMutation = useTriggerAIEvaluationForCandidateMutation(
    selected.candidate_id,
    jobId,
  )
  const preliminary = selected.preliminary_evaluation

  return (
    <PanelShell>
      <p className="eyebrow normal-case text-ink-400">Reviewing this candidate…</p>

      {preliminary && (
        <div className="rounded-md border border-border bg-cream-100 px-3 py-2 text-sm text-ink-600">
          <p className="eyebrow text-ink-400">Preliminary pre-screen (not a final decision)</p>
          <p className="mt-1">
            {preliminary.status === 'completed' && preliminary.score !== null
              ? `Automated keyword match scored this resume ${Math.round(Number(preliminary.score))}/100 — the complete AI evaluation above replaces this once it finishes.`
              : 'The automated preliminary pre-screen for this resume hasn’t finished either.'}
          </p>
        </div>
      )}

      <button
        type="button"
        onClick={() => triggerMutation.mutate(selected.application_id)}
        disabled={triggerMutation.isPending}
        className="btn-secondary self-start"
      >
        {triggerMutation.isPending ? 'Checking…' : 'Check again'}
      </button>

      {triggerMutation.isError && (
        <p role="alert" className="text-sm text-red-700">
          {triggerMutation.error.message}
        </p>
      )}
    </PanelShell>
  )
}

function LoadedPanel({
  jobId,
  selected,
}: {
  jobId: string
  selected: CandidatePoolEntry
}) {
  const detailQuery = useCandidateDetailQuery(selected.candidate_id)

  if (detailQuery.isLoading) {
    return (
      <PanelShell>
        <div className="h-48 animate-pulse rounded-md bg-cream-100" />
      </PanelShell>
    )
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <PanelShell>
        <p role="alert" className="text-sm text-red-700">
          Couldn't load this candidate's evaluation. Try selecting them again.
        </p>
      </PanelShell>
    )
  }

  const application = detailQuery.data.applications.find(
    (a) => a.application_id === selected.application_id,
  )
  const evaluation = application?.evaluations.find(
    (e) => e.stage === 'ai' && e.status === 'completed',
  )

  if (!application || !evaluation) {
    return <ReviewingState jobId={jobId} selected={selected} />
  }

  return (
    <CompletedPanel
      jobId={jobId}
      candidateId={detailQuery.data.id}
      application={application}
      evaluation={evaluation}
    />
  )
}

function CompletedPanel({
  jobId,
  candidateId,
  application,
  evaluation,
}: {
  jobId: string
  candidateId: string
  application: ApplicationDetail
  evaluation: Evaluation
}) {
  const mandatory = evaluation.requirement_results.filter(
    (r) => r.requirement_category === 'mandatory',
  )
  const preferred = evaluation.requirement_results.filter(
    (r) => r.requirement_category === 'preferred',
  )
  const baselineMet = mandatory.filter((r) => r.status === 'met').length
  const baselineTotal = mandatory.length
  const standoutsCount = evaluation.strengths_json.length
  const toVerifyCount = evaluation.questions_json.length
  const score = evaluation.score !== null ? Number(evaluation.score) : 0

  return (
    <div className="card flex min-w-0 flex-col gap-6 p-6">
      <div className="flex min-w-0 items-start gap-4">
        <FitGauge score={score} />
        <div className="min-w-0">
          <p className="eyebrow text-terracotta-600">{fitQualityLabel(score)}</p>
          <h2 className="mt-1 text-xl break-words text-ink">{application.resume_filename}</h2>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm text-ink-400">
            <span>Applied for {application.job_title}</span>
            <span>·</span>
            <a
              href={`${API_BASE_URL}/api/resumes/${application.resume_id}/file`}
              target="_blank"
              rel="noreferrer"
              className="text-terracotta underline"
            >
              View resume
            </a>
          </div>
        </div>
      </div>

      <p className="text-sm text-ink-600">
        This candidate meets {baselineMet} of {baselineTotal} baseline requirement
        {baselineTotal === 1 ? '' : 's'}
        {preferred.length > 0
          ? `, with ${preferred.filter((r) => r.status === 'met').length} of ${preferred.length} preferred requirements also met`
          : ''}
        . The evaluation surfaced {standoutsCount} standout strength
        {standoutsCount === 1 ? '' : 's'} and {toVerifyCount} item
        {toVerifyCount === 1 ? '' : 's'} worth verifying directly.
      </p>

      <div className="border-l-2 border-terracotta pl-3">
        <p className="eyebrow">Why this score</p>
        <p className="mt-1 text-sm text-ink-600">
          Baseline (mandatory) requirements carry 70% of the score, preferred
          requirements 20%, and verified strengths up to 10% — all backed by
          evidence quoted directly from the resume. See the breakdown below
          for exactly which evidence drove it.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <StatTile value={`${baselineMet}/${baselineTotal}`} label="Baseline met" />
        <StatTile value={standoutsCount} label="Standouts" />
        <StatTile value={toVerifyCount} label="To verify" />
      </div>

      <DecisionButtons
        jobId={jobId}
        candidateId={candidateId}
        applicationId={application.application_id}
        decision={application.decision}
      />

      <RequirementEvidenceList title="Baseline requirements" results={mandatory} />
      <RequirementEvidenceList title="Nice to have" results={preferred} />

      <div>
        <h3 className="eyebrow mb-2">What stands out</h3>
        <StandoutsList strengths={evaluation.strengths_json} />
      </div>

      <div>
        <h3 className="eyebrow mb-1">Gaps &amp; things to verify</h3>
        <p className="mb-2 text-xs text-ink-400">Not disqualifiers — prompts for you</p>
        <GapsList questions={evaluation.questions_json} />
      </div>
    </div>
  )
}

function StatTile({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="rounded-md border border-border bg-cream-100 px-3 py-3 text-center">
      <p className="font-display text-xl text-ink">{value}</p>
      <p className="eyebrow mt-0.5">{label}</p>
    </div>
  )
}
