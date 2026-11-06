import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteApplication,
  getCandidateDetail,
  getCandidatePool,
  triggerAIEvaluation,
  updateDecision,
  updateReviewStatus,
} from './api'
import type {
  CandidateDecision,
  CandidatePoolQuery,
  ReviewStatus,
} from '../../types/candidate'

export function useCandidatePoolQuery(
  jobId: string,
  query: CandidatePoolQuery,
) {
  return useQuery({
    queryKey: ['jobs', jobId, 'candidates', query],
    queryFn: () => getCandidatePool(jobId, query),
    placeholderData: (previous) => previous,
  })
}

const BOARD_QUERY: CandidatePoolQuery = {
  page: 1,
  pageSize: 100,
  sortBy: 'score',
  sortDir: 'desc',
  search: '',
  minScore: '',
  requirementStatus: '',
  reviewStatus: '',
}

/** The merged job-detail board shows every candidate on one screen, ranked
 * best-first — no filters or pagination, matching the single reviewing
 * queue the hiring manager watches resume by resume. */
export function useCandidateBoardQuery(jobId: string) {
  return useCandidatePoolQuery(jobId, BOARD_QUERY)
}

export const candidateDetailQueryKey = (candidateId: string) =>
  ['candidates', candidateId] as const

export function useCandidateDetailQuery(candidateId: string) {
  return useQuery({
    queryKey: candidateDetailQueryKey(candidateId),
    queryFn: () => getCandidateDetail(candidateId),
  })
}

export function useTriggerAIEvaluationForCandidateMutation(
  candidateId: string,
  jobId?: string,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (applicationId: string) => triggerAIEvaluation(applicationId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: candidateDetailQueryKey(candidateId),
      })
      // Also refresh the board query — triggering/retrying from the board's
      // "Reviewing…" state only has an effect the user can see if the
      // board's own cached ai_evaluation summary picks up the result too.
      if (jobId) {
        void queryClient.invalidateQueries({ queryKey: ['jobs', jobId, 'candidates'] })
      }
    },
  })
}

export function useUpdateDecisionMutation(jobId: string, candidateId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      applicationId,
      decision,
    }: {
      applicationId: string
      decision: CandidateDecision | null
    }) => updateDecision(applicationId, decision),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['jobs', jobId, 'candidates'] })
      void queryClient.invalidateQueries({ queryKey: candidateDetailQueryKey(candidateId) })
    },
  })
}

export function useDeleteApplicationMutation(jobId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (applicationId: string) => deleteApplication(applicationId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['jobs', jobId, 'candidates'] })
    },
  })
}

export function useUpdateReviewStatusMutation(candidateId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      applicationId,
      reviewStatus,
    }: {
      applicationId: string
      reviewStatus: ReviewStatus
    }) => updateReviewStatus(applicationId, reviewStatus),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: candidateDetailQueryKey(candidateId),
      })
    },
  })
}
