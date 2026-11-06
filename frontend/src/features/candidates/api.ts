import { apiRequest } from '../../api/client'
import type {
  CandidateDecision,
  CandidatePoolQuery,
  CandidatePoolResponse,
  ReviewStatus,
} from '../../types/candidate'
import type { CandidateDetail } from '../../types/candidateDetail'
import type { Evaluation } from '../../types/evaluation'

export function getCandidatePool(
  jobId: string,
  query: CandidatePoolQuery,
): Promise<CandidatePoolResponse> {
  const params = new URLSearchParams({
    page: String(query.page),
    page_size: String(query.pageSize),
    sort_by: query.sortBy,
    sort_dir: query.sortDir,
  })
  if (query.search) params.set('search', query.search)
  if (query.minScore) params.set('min_score', query.minScore)
  if (query.requirementStatus)
    params.set('requirement_status', query.requirementStatus)
  if (query.reviewStatus) params.set('review_status', query.reviewStatus)

  return apiRequest<CandidatePoolResponse>(
    `/api/jobs/${jobId}/candidates?${params.toString()}`,
  )
}

export function triggerAIEvaluation(applicationId: string): Promise<Evaluation> {
  return apiRequest<Evaluation>(`/api/applications/${applicationId}/evaluations`, {
    method: 'POST',
  })
}

export function getCandidateDetail(
  candidateId: string,
): Promise<CandidateDetail> {
  return apiRequest<CandidateDetail>(`/api/candidates/${candidateId}`)
}

export function updateReviewStatus(
  applicationId: string,
  reviewStatus: ReviewStatus,
): Promise<unknown> {
  return apiRequest(`/api/applications/${applicationId}/review-status`, {
    method: 'PATCH',
    body: JSON.stringify({ review_status: reviewStatus }),
  })
}

export function updateDecision(
  applicationId: string,
  decision: CandidateDecision | null,
): Promise<unknown> {
  return apiRequest(`/api/applications/${applicationId}/decision`, {
    method: 'PATCH',
    body: JSON.stringify({ decision }),
  })
}

export function deleteApplication(applicationId: string): Promise<void> {
  return apiRequest<void>(`/api/applications/${applicationId}`, { method: 'DELETE' })
}
