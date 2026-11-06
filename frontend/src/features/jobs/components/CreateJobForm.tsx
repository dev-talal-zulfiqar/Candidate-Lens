import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { useCreateJobMutation } from '../hooks'
import { MarkdownPreview } from './MarkdownPreview'

const createJobSchema = z.object({
  title: z.string().trim().min(1, 'Title is required').max(200),
  description_md: z
    .string()
    .trim()
    .min(1, 'Job description is required')
    .max(20_000, 'Job description is too long'),
})

type CreateJobFormValues = z.infer<typeof createJobSchema>

interface CreateJobFormProps {
  onCreated: (jobId: string) => void
}

export function CreateJobForm({ onCreated }: CreateJobFormProps) {
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<CreateJobFormValues>({
    resolver: zodResolver(createJobSchema),
    defaultValues: { title: '', description_md: '' },
  })
  const createJobMutation = useCreateJobMutation()
  const [descriptionMode, setDescriptionMode] = useState<'write' | 'preview'>(
    'write',
  )
  const descriptionValue = watch('description_md')

  const onSubmit = handleSubmit(async (values) => {
    try {
      const job = await createJobMutation.mutateAsync(values)
      reset()
      setDescriptionMode('write')
      onCreated(job.id)
    } catch {
      // Already surfaced to the user via createJobMutation.isError below —
      // this only stops the rejection from becoming an unhandled promise
      // rejection, since the form's onSubmit handler isn't awaited by React.
    }
  })

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-5">
      <div className="flex flex-col gap-1.5">
        <label htmlFor="job-title" className="eyebrow">
          Job title
        </label>
        <input
          id="job-title"
          type="text"
          placeholder="e.g. Senior Backend Engineer"
          className="rounded-md border border-border-strong bg-cream px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none focus:ring-1 focus:ring-terracotta"
          {...register('title')}
        />
        {errors.title && (
          <p className="text-sm text-red-600">{errors.title.message}</p>
        )}
      </div>

      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <label htmlFor="job-description" className="eyebrow">
            Job description
          </label>
          <div
            role="group"
            aria-label="Description view"
            className="inline-flex rounded-md border border-border-strong text-xs font-medium"
          >
            <button
              type="button"
              onClick={() => setDescriptionMode('write')}
              aria-pressed={descriptionMode === 'write'}
              className={`rounded-l-md px-2.5 py-1 ${
                descriptionMode === 'write'
                  ? 'bg-ink text-cream'
                  : 'text-ink-600 hover:bg-cream-100'
              }`}
            >
              Write
            </button>
            <button
              type="button"
              onClick={() => setDescriptionMode('preview')}
              aria-pressed={descriptionMode === 'preview'}
              className={`rounded-r-md border-l border-border-strong px-2.5 py-1 ${
                descriptionMode === 'preview'
                  ? 'bg-ink text-cream'
                  : 'text-ink-600 hover:bg-cream-100'
              }`}
            >
              Preview
            </button>
          </div>
        </div>

        <textarea
          id="job-description"
          rows={10}
          placeholder={
            'Paste the job posting as-is, or write it yourself — plain text or Markdown both work, e.g.\n\n## Requirements\n- 5+ years of backend experience\n- PostgreSQL'
          }
          className={`rounded-md border border-border-strong bg-cream px-3 py-2 font-mono text-sm text-ink focus:border-terracotta focus:outline-none focus:ring-1 focus:ring-terracotta ${
            descriptionMode === 'write' ? '' : 'hidden'
          }`}
          {...register('description_md')}
        />
        {descriptionMode === 'write' && (
          <p className="text-xs text-ink-400">
            Plain text works fine — Markdown (## headings, - bullets) is
            optional, just renders nicer in Preview.
          </p>
        )}
        {descriptionMode === 'preview' && (
          <div className="min-h-[15rem] rounded-md border border-border-strong bg-paper px-3 py-2">
            {descriptionValue?.trim() ? (
              <MarkdownPreview markdown={descriptionValue} />
            ) : (
              <p className="text-sm text-ink-400">Nothing to preview yet.</p>
            )}
          </div>
        )}

        {errors.description_md && (
          <p className="text-sm text-red-600">
            {errors.description_md.message}
          </p>
        )}
      </div>

      {createJobMutation.isError && (
        <p
          role="alert"
          className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {createJobMutation.error.message}
        </p>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        className="btn-primary self-start"
      >
        {isSubmitting ? 'Creating…' : 'Create job'}
      </button>
    </form>
  )
}
