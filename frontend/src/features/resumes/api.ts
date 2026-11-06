import { apiRequest } from '../../api/client'
import type { UploadBatch } from '../../types/upload'

export function uploadResumes(jobId: string, files: File[]): Promise<UploadBatch> {
  const formData = new FormData()
  for (const file of files) {
    formData.append('files', file)
  }
  return apiRequest<UploadBatch>(`/api/jobs/${jobId}/resumes`, {
    method: 'POST',
    body: formData,
    // Validation/storage/extraction now runs as a background task, not
    // inline with this request — but the request body (every file's
    // bytes) still has to finish transferring before this returns, which
    // for a large batch can itself take a while on a slow connection.
    timeoutMs: 60_000,
  })
}

export function getUploadBatch(jobId: string, batchId: string): Promise<UploadBatch> {
  return apiRequest<UploadBatch>(`/api/jobs/${jobId}/batches/${batchId}`)
}
