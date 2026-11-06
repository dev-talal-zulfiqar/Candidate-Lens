export type BatchStatus =
  'pending' | 'processing' | 'completed' | 'partial' | 'failed'
export type ResumeOutcomeStatus = 'processed' | 'duplicate' | 'failed'

export interface ResumeUploadResult {
  filename: string
  status: ResumeOutcomeStatus
  candidate_id: string | null
  resume_id: string | null
  application_id: string | null
  error: string | null
}

// Upload processing runs as a background task, not inline with the POST
// that creates it — results start empty and fill in as files finish; poll
// GET .../batches/{id} (same shape) until status is no longer "processing".
export interface UploadBatch {
  id: string
  job_id: string
  status: BatchStatus
  total_count: number
  processed_count: number
  failed_count: number
  created_at: string
  completed_at: string | null
  results: ResumeUploadResult[]
}
