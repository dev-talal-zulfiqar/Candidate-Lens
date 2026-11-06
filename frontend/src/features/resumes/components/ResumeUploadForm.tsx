import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { UploadBatch } from '../../../types/upload'
import { jobQueryKey, jobsQueryKey } from '../../jobs/hooks'
import { useUploadBatchQuery, useUploadResumesMutation } from '../hooks'

const ACCEPTED_EXTENSIONS = ['.pdf', '.docx']
const MAX_SIZE_BYTES = 5 * 1024 * 1024 // Mirrors the backend's default max_upload_size_mb.
const MAX_FILES_PER_UPLOAD = 500 // Mirrors the backend's default max_files_per_upload.

interface FileCheck {
  file: File
  valid: boolean
  reason?: string
}

function checkFile(file: File): FileCheck {
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!ACCEPTED_EXTENSIONS.includes(extension)) {
    return {
      file,
      valid: false,
      reason: 'Only .pdf and .docx files are accepted',
    }
  }
  if (file.size === 0) {
    return { file, valid: false, reason: 'File is empty' }
  }
  if (file.size > MAX_SIZE_BYTES) {
    return { file, valid: false, reason: 'File exceeds the 5 MB limit' }
  }
  return { file, valid: true }
}

const TERMINAL_BATCH_STATUSES = new Set(['completed', 'partial', 'failed'])

interface ResumeUploadFormProps {
  jobId: string
  onUploaded: (batch: UploadBatch) => void
}

export function ResumeUploadForm({ jobId, onUploaded }: ResumeUploadFormProps) {
  const [checks, setChecks] = useState<FileCheck[]>([])
  const [isDragOver, setIsDragOver] = useState(false)
  const [batchId, setBatchId] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()
  const uploadMutation = useUploadResumesMutation(jobId)
  const batchQuery = useUploadBatchQuery(jobId, batchId)

  const validFiles = checks.filter((c) => c.valid)
  const invalidFiles = checks.filter((c) => !c.valid)
  const tooManyFiles = checks.length > MAX_FILES_PER_UPLOAD

  // Processing happens in the background — this effect notices when the
  // batch we're watching reaches a terminal status, hands the final
  // result to the caller, and refreshes everything the upload could have
  // changed (job requirement counts, the job list, the candidate board).
  useEffect(() => {
    const batch = batchQuery.data
    if (!batch || !TERMINAL_BATCH_STATUSES.has(batch.status)) return
    onUploaded(batch)
    void queryClient.invalidateQueries({ queryKey: jobQueryKey(jobId) })
    void queryClient.invalidateQueries({ queryKey: jobsQueryKey })
    void queryClient.invalidateQueries({ queryKey: ['jobs', jobId, 'candidates'] })
    setBatchId(null)
    // onUploaded is passed fresh each render by the caller — depending on
    // it here would re-fire this effect without the batch itself changing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchQuery.data, jobId, queryClient])

  const handleFilesSelected = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return
    setChecks(Array.from(fileList).map(checkFile))
    uploadMutation.reset()
  }

  const handleUpload = async () => {
    if (validFiles.length === 0 || tooManyFiles) return
    try {
      const batch = await uploadMutation.mutateAsync(validFiles.map((c) => c.file))
      setChecks([])
      setBatchId(batch.id)
      if (inputRef.current) inputRef.current.value = ''
    } catch {
      // Already surfaced via uploadMutation.isError below — this only
      // stops the rejection from becoming an unhandled promise rejection.
    }
  }

  if (batchId) {
    const batch = batchQuery.data
    const done = batch ? batch.processed_count + batch.failed_count : 0
    return (
      <div className="flex flex-col gap-2 rounded-lg border border-dashed border-border-strong bg-cream-100 px-6 py-8 text-center">
        <span className="font-display text-base text-ink">
          Processing resumes…
        </span>
        <span className="eyebrow normal-case">
          {batch ? `${done} of ${batch.total_count} done` : 'Starting…'}
        </span>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <label
        htmlFor="resume-files"
        onDragOver={(event) => {
          event.preventDefault()
          setIsDragOver(true)
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={(event) => {
          event.preventDefault()
          setIsDragOver(false)
          handleFilesSelected(event.dataTransfer.files)
        }}
        className={`flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors ${
          isDragOver
            ? 'border-terracotta bg-terracotta-50'
            : 'border-border-strong bg-cream-100 hover:bg-cream-200/60'
        }`}
      >
        <span className="font-display text-base text-ink">
          Drag &amp; drop resumes here
        </span>
        <span className="eyebrow normal-case">
          or <span className="text-terracotta underline">browse</span> — PDF
          or DOCX, up to 5 MB each
        </span>
        <input
          id="resume-files"
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.docx"
          onChange={(event) => handleFilesSelected(event.target.files)}
          className="sr-only"
        />
      </label>

      {tooManyFiles && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {checks.length} files selected — at most {MAX_FILES_PER_UPLOAD} can be uploaded at
          once. Remove some and try again, or split this into multiple uploads.
        </p>
      )}

      {checks.length > 0 && (
        <ul className="flex flex-col gap-1 text-sm">
          {checks.map((check, index) => (
            <li
              key={`${check.file.name}-${index}`}
              className={`flex items-center justify-between rounded-md px-3 py-1.5 ${
                check.valid ? 'bg-cream-100 text-ink-600' : 'bg-red-50 text-red-700'
              }`}
            >
              <span>{check.file.name}</span>
              <span>{check.valid ? 'Ready' : check.reason}</span>
            </li>
          ))}
        </ul>
      )}

      {invalidFiles.length > 0 && (
        <p className="text-sm text-amber-700">
          {invalidFiles.length} {invalidFiles.length === 1 ? 'file' : 'files'}{' '}
          will be skipped — fix them above or they won't be uploaded.
        </p>
      )}

      {validFiles.length > 0 && !tooManyFiles && (
        <button
          type="button"
          onClick={handleUpload}
          disabled={uploadMutation.isPending}
          className="btn-primary self-start"
        >
          {uploadMutation.isPending
            ? 'Starting upload…'
            : `Upload ${validFiles.length} ${validFiles.length === 1 ? 'resume' : 'resumes'}`}
        </button>
      )}

      {uploadMutation.isError && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {uploadMutation.error.message}
        </p>
      )}
    </div>
  )
}
