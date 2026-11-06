import { apiRequest } from '../../api/client'
import type {
  Job,
  JobCreateInput,
  JobRequirement,
  JobRequirementInput,
  JobSummary,
  RequirementSuggestion,
} from '../../types/job'

export function listJobs(): Promise<JobSummary[]> {
  return apiRequest<JobSummary[]>('/api/jobs')
}

export function getJob(jobId: string): Promise<Job> {
  return apiRequest<Job>(`/api/jobs/${jobId}`)
}

export function createJob(input: JobCreateInput): Promise<Job> {
  return apiRequest<Job>('/api/jobs', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function createRequirements(
  jobId: string,
  requirements: JobRequirementInput[],
): Promise<JobRequirement[]> {
  return apiRequest<JobRequirement[]>(`/api/jobs/${jobId}/requirements`, {
    method: 'POST',
    body: JSON.stringify({ requirements }),
  })
}

export function editRequirements(
  jobId: string,
  requirements: JobRequirementInput[],
): Promise<JobRequirement[]> {
  return apiRequest<JobRequirement[]>(`/api/jobs/${jobId}/requirements`, {
    method: 'PUT',
    body: JSON.stringify({ requirements }),
    // Redoes both evaluation stages for every candidate synchronously —
    // can run well past the default timeout until this moves to
    // background processing.
    timeoutMs: 120_000,
  })
}

export function inferRequirements(jobId: string): Promise<RequirementSuggestion[]> {
  return apiRequest<RequirementSuggestion[]>(`/api/jobs/${jobId}/requirements/infer`, {
    method: 'POST',
  })
}

export function deleteJob(jobId: string): Promise<void> {
  return apiRequest<void>(`/api/jobs/${jobId}`, { method: 'DELETE' })
}

export function rerunEvaluations(jobId: string): Promise<void> {
  return apiRequest<void>(`/api/jobs/${jobId}/evaluations/rerun`, {
    method: 'POST',
    // Redoes both evaluation stages for every candidate synchronously —
    // can run well past the default timeout until this moves to
    // background processing.
    timeoutMs: 120_000,
  })
}
