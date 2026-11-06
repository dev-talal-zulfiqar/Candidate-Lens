import { useQuery, useMutation } from '@tanstack/react-query'
import { getUploadBatch, uploadResumes } from './api'

export function useUploadResumesMutation(jobId: string) {
  return useMutation({
    mutationFn: (files: File[]) => uploadResumes(jobId, files),
  })
}

const TERMINAL_BATCH_STATUSES = new Set(['completed', 'partial', 'failed'])

/** Polls an upload batch while it's still processing in the background,
 * stopping as soon as it reaches a terminal status. */
export function useUploadBatchQuery(jobId: string, batchId: string | null) {
  return useQuery({
    queryKey: ['jobs', jobId, 'batches', batchId],
    queryFn: () => getUploadBatch(jobId, batchId as string),
    enabled: batchId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && TERMINAL_BATCH_STATUSES.has(status) ? false : 1000
    },
  })
}
