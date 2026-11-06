import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useState } from 'react'
import { useFieldArray, useForm } from 'react-hook-form'
import { z } from 'zod'
import { ApiError } from '../../../api/client'
import { useToast } from '../../../components/useToast'
import type { JobRequirement } from '../../../types/job'
import {
  useCreateRequirementsMutation,
  useEditRequirementsMutation,
  useInferRequirementsMutation,
} from '../hooks'

const requirementSchema = z.object({
  description: z.string().trim().min(1, 'Required').max(2_000),
  category: z.enum(['mandatory', 'preferred']),
  weight: z.coerce
    .number()
    .positive('Weight must be greater than 0')
    .max(10, 'Weight must be 10 or less'),
})

const requirementsFormSchema = z.object({
  requirements: z
    .array(requirementSchema)
    .min(1, 'Add at least one requirement'),
})

type RequirementsFormInput = z.input<typeof requirementsFormSchema>
type RequirementsFormValues = z.output<typeof requirementsFormSchema>

interface RequirementsEditorProps {
  jobId: string
  /** When present, this edits an already-confirmed rubric instead of
   * setting one up for the first time — skips the AI/manual choice screen
   * (there's already a list to start from) and saves through the edit
   * endpoint, which resets this job's evaluation history. */
  existing?: JobRequirement[]
  onCancel?: () => void
  onSaved?: () => void
}

export function RequirementsEditor({
  jobId,
  existing,
  onCancel,
  onSaved,
}: RequirementsEditorProps) {
  const isEditing = existing !== undefined
  const [mode, setMode] = useState<'choice' | 'form'>(isEditing ? 'form' : 'choice')
  const [source, setSource] = useState<'ai' | 'manual'>('manual')
  const { showToast } = useToast()
  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<RequirementsFormInput, unknown, RequirementsFormValues>({
    resolver: zodResolver(requirementsFormSchema),
    defaultValues: {
      requirements: isEditing
        ? existing.map((r) => ({
            description: r.description,
            category: r.category,
            weight: Number(r.weight),
          }))
        : [{ description: '', category: 'mandatory', weight: 1 }],
    },
  })
  const { fields, append, remove } = useFieldArray({
    control,
    name: 'requirements',
  })
  const createRequirementsMutation = useCreateRequirementsMutation(jobId)
  const editRequirementsMutation = useEditRequirementsMutation(jobId)
  const inferRequirementsMutation = useInferRequirementsMutation(jobId)
  const saveMutation = isEditing ? editRequirementsMutation : createRequirementsMutation

  useEffect(() => {
    if (inferRequirementsMutation.error instanceof ApiError
      && inferRequirementsMutation.error.status === 402) {
      showToast(inferRequirementsMutation.error.message)
    }
  }, [inferRequirementsMutation.error, showToast])

  const onSubmit = handleSubmit(async (values) => {
    try {
      await saveMutation.mutateAsync(values.requirements)
      onSaved?.()
    } catch {
      // Already surfaced via saveMutation.isError below — this only stops
      // the rejection from becoming an unhandled promise rejection, since
      // the form's onSubmit handler isn't awaited by React.
    }
  })

  const handleGenerateWithAI = async () => {
    try {
      const suggestions = await inferRequirementsMutation.mutateAsync()
      reset({
        requirements: suggestions.map((s) => ({
          description: s.description,
          category: s.category,
          weight: Number(s.weight),
        })),
      })
      setSource('ai')
      setMode('form')
    } catch {
      // Already surfaced via the effect above (402) and
      // inferRequirementsMutation.isError below for other failures.
    }
  }

  if (mode === 'choice') {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-sm text-ink-600">
          Start from what the AI reads in the job description, or build the
          list yourself.
        </p>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleGenerateWithAI}
            disabled={inferRequirementsMutation.isPending}
            className="btn-primary"
          >
            {inferRequirementsMutation.isPending
              ? 'Reading the job description…'
              : '✨ Generate with AI'}
          </button>
          <button
            type="button"
            onClick={() => setMode('form')}
            className="btn-secondary"
          >
            Add manually
          </button>
        </div>
        {inferRequirementsMutation.isError && (
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {inferRequirementsMutation.error.message}
          </p>
        )}
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      {source === 'ai' && (
        <p className="eyebrow normal-case text-terracotta-600">
          Generated from the job description — review before confirming
        </p>
      )}
      {isEditing && (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Saving replaces the current rubric and clears every candidate's
          evaluation for this job — scores will be recomputed against the
          new requirements.
        </p>
      )}
      <div className="flex flex-col gap-3">
        {fields.map((field, index) => (
          <div
            key={field.id}
            className="grid grid-cols-[1fr_auto_auto_auto] items-start gap-2 rounded-md border border-border p-3"
          >
            <div className="flex flex-col gap-1">
              <label
                className="sr-only"
                htmlFor={`req-description-${field.id}`}
              >
                Requirement description
              </label>
              <input
                id={`req-description-${field.id}`}
                type="text"
                placeholder="e.g. 5+ years of Python experience"
                className="rounded-md border border-border-strong bg-cream px-2 py-1.5 text-sm text-ink focus:border-terracotta focus:outline-none focus:ring-1 focus:ring-terracotta"
                {...register(`requirements.${index}.description`)}
              />
              {errors.requirements?.[index]?.description && (
                <p className="text-xs text-red-600">
                  {errors.requirements[index]?.description?.message}
                </p>
              )}
            </div>

            <div className="flex flex-col gap-1">
              <label className="sr-only" htmlFor={`req-category-${field.id}`}>
                Category
              </label>
              <select
                id={`req-category-${field.id}`}
                className="rounded-md border border-border-strong bg-cream px-2 py-1.5 text-sm text-ink focus:border-terracotta focus:outline-none focus:ring-1 focus:ring-terracotta"
                {...register(`requirements.${index}.category`)}
              >
                <option value="mandatory">Mandatory</option>
                <option value="preferred">Preferred</option>
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label className="sr-only" htmlFor={`req-weight-${field.id}`}>
                Weight
              </label>
              <input
                id={`req-weight-${field.id}`}
                type="number"
                step="0.1"
                min="0.1"
                max="10"
                placeholder="Weight"
                className="w-20 rounded-md border border-border-strong bg-cream px-2 py-1.5 text-sm text-ink focus:border-terracotta focus:outline-none focus:ring-1 focus:ring-terracotta"
                {...register(`requirements.${index}.weight`)}
              />
              {errors.requirements?.[index]?.weight && (
                <p className="text-xs text-red-600">
                  {errors.requirements[index]?.weight?.message}
                </p>
              )}
            </div>

            <button
              type="button"
              onClick={() => remove(index)}
              disabled={fields.length === 1}
              aria-label="Remove requirement"
              className="rounded-md px-2 py-1.5 text-sm text-ink-400 hover:bg-cream-100 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      {errors.requirements?.root && (
        <p className="text-sm text-red-600">
          {errors.requirements.root.message}
        </p>
      )}

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() =>
            append({ description: '', category: 'mandatory', weight: 1 })
          }
          className="btn-secondary"
        >
          Add requirement
        </button>

        <button
          type="submit"
          disabled={isSubmitting}
          className="btn-primary"
        >
          {isSubmitting
            ? isEditing
              ? 'Saving…'
              : 'Confirming…'
            : isEditing
              ? 'Save changes'
              : 'Confirm requirements'}
        </button>

        {isEditing && onCancel && (
          <button type="button" onClick={onCancel} className="text-sm text-ink-400 underline">
            Cancel
          </button>
        )}
      </div>

      {saveMutation.isError && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {saveMutation.error.message}
        </p>
      )}
    </form>
  )
}
