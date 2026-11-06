import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createJob,
  createRequirements,
  deleteJob,
  editRequirements,
  getJob,
  inferRequirements,
  listJobs,
  rerunEvaluations,
} from './api'
import type { JobCreateInput, JobRequirementInput } from '../../types/job'

export const jobsQueryKey = ['jobs'] as const
export const jobQueryKey = (jobId: string) => ['jobs', jobId] as const

export function useJobsQuery() {
  return useQuery({ queryKey: jobsQueryKey, queryFn: listJobs })
}

export function useJobQuery(jobId: string) {
  return useQuery({
    queryKey: jobQueryKey(jobId),
    queryFn: () => getJob(jobId),
  })
}

export function useCreateJobMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: JobCreateInput) => createJob(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: jobsQueryKey })
    },
  })
}

export function useInferRequirementsMutation(jobId: string) {
  return useMutation({
    mutationFn: () => inferRequirements(jobId),
  })
}

export function useCreateRequirementsMutation(jobId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (requirements: JobRequirementInput[]) =>
      createRequirements(jobId, requirements),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: jobQueryKey(jobId) })
      void queryClient.invalidateQueries({ queryKey: jobsQueryKey })
    },
  })
}

export function useEditRequirementsMutation(jobId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (requirements: JobRequirementInput[]) => editRequirements(jobId, requirements),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: jobQueryKey(jobId) })
      void queryClient.invalidateQueries({ queryKey: jobsQueryKey })
      void queryClient.invalidateQueries({ queryKey: ['jobs', jobId, 'candidates'] })
    },
  })
}

export function useDeleteJobMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (jobId: string) => deleteJob(jobId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: jobsQueryKey })
    },
  })
}

export function useRerunEvaluationsMutation(jobId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => rerunEvaluations(jobId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['jobs', jobId, 'candidates'] })
    },
  })
}
