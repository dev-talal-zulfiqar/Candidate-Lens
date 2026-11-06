export type EvaluationStatus = 'pending' | 'running' | 'completed' | 'failed'
export type ExtractionStatus = 'pending' | 'completed' | 'failed'
export type ReviewStatus = 'unreviewed' | 'in_review' | 'reviewed'
export type RequirementResultStatus = 'met' | 'not_met' | 'unverified'
export type CandidateDecision = 'advance' | 'hold' | 'decline'

export interface EvaluationSummary {
  status: EvaluationStatus
  score: string | null
  coverage_score: string | null
  completed_at: string | null
}

export interface BaselineSummary {
  met: number
  total: number
}

export interface CandidatePoolEntry {
  application_id: string
  candidate_id: string
  display_name: string | null
  resume_filename: string
  extraction_status: ExtractionStatus
  review_status: ReviewStatus
  decision: CandidateDecision | null
  created_at: string
  preliminary_evaluation: EvaluationSummary | null
  ai_evaluation: EvaluationSummary | null
  baseline: BaselineSummary | null
}

export interface CandidatePoolSummary {
  total_applications: number
  extraction_completed: number
  extraction_failed: number
}

export interface CandidatePoolResponse {
  items: CandidatePoolEntry[]
  page: number
  page_size: number
  total: number
  summary: CandidatePoolSummary
}

export type SortBy = 'score' | 'created_at' | 'display_name'
export type SortDir = 'asc' | 'desc'

export interface CandidatePoolQuery {
  page: number
  pageSize: number
  sortBy: SortBy
  sortDir: SortDir
  search: string
  minScore: string
  requirementStatus: RequirementResultStatus | ''
  reviewStatus: ReviewStatus | ''
}
