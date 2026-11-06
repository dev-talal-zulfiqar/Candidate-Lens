import type { Evaluation } from './evaluation'
import type { CandidateDecision, ExtractionStatus, ReviewStatus } from './candidate'

export interface ApplicationDetail {
  application_id: string
  job_id: string
  job_title: string
  resume_id: string
  resume_filename: string
  extraction_status: ExtractionStatus
  review_status: ReviewStatus
  decision: CandidateDecision | null
  created_at: string
  evaluations: Evaluation[]
}

export interface CandidateDetail {
  id: string
  display_name: string | null
  created_at: string
  applications: ApplicationDetail[]
}
