import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../../api/client'
import { AI_CREDITS_EXHAUSTED_MESSAGE } from '../../api/constants'
import type { CandidatePoolEntry } from '../../types/candidate'
import { triggerAIEvaluation } from './api'

/**
 * Drives AI evaluation for every eligible candidate automatically, one at a
 * time, so the hiring manager never has to click a per-row button — upload
 * resumes and the queue reviews them. Processed ids are remembered in
 * `attempted` so a transient failure doesn't get silently retried forever;
 * `restart()` is the explicit, user-initiated way to give failed attempts
 * another shot (also what recovers a queue that stalled before a page
 * refresh, since all of this state is in-memory only).
 *
 * A credits-exhausted failure is treated differently from an ordinary
 * per-candidate failure: it's an operations problem (the OpenAI account is
 * out of quota, or the key is revoked), not something specific to one
 * resume, and every other queued item would fail identically. So instead
 * of grinding through the rest of the queue one doomed request at a time,
 * the queue drains itself immediately and surfaces `creditsExhausted` once
 * for the caller to show a single toast.
 */
export function useEvaluationQueue(
  jobId: string,
  items: CandidatePoolEntry[],
  canEvaluate: boolean,
) {
  const queryClient = useQueryClient()
  const [reviewing, setReviewing] = useState<Set<string>>(new Set())
  const [errored, setErrored] = useState<Set<string>>(new Set())
  const [creditsExhausted, setCreditsExhausted] = useState(false)
  const processingRef = useRef(false)
  const queueRef = useRef<string[]>([])
  const attemptedRef = useRef<Set<string>>(new Set())
  const processNextRef = useRef<() => void>(() => {})

  const isEligible = useCallback(
    (item: CandidatePoolEntry) =>
      canEvaluate &&
      item.extraction_status === 'completed' &&
      item.ai_evaluation === null,
    [canEvaluate],
  )

  const handleCreditsExhausted = useCallback(() => {
    const stillQueued = queueRef.current
    queueRef.current = []
    setCreditsExhausted(true)
    setReviewing(new Set())
    // Release everything that never got a real attempt so a later
    // restart() (once an admin fixes the key) retries them — only the id
    // that actually failed stays "attempted".
    stillQueued.forEach((id) => attemptedRef.current.delete(id))
  }, [])

  const processNext = useCallback(() => {
    if (processingRef.current) return
    const nextId = queueRef.current.shift()
    if (!nextId) return
    processingRef.current = true

    triggerAIEvaluation(nextId)
      .then((evaluation) => {
        if (evaluation.status !== 'completed') {
          if (evaluation.error_message === AI_CREDITS_EXHAUSTED_MESSAGE) {
            handleCreditsExhausted()
          } else {
            setErrored((prev) => new Set(prev).add(nextId))
          }
        }
        void queryClient.invalidateQueries({ queryKey: ['jobs', jobId, 'candidates'] })
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 402) {
          handleCreditsExhausted()
        } else {
          setErrored((prev) => new Set(prev).add(nextId))
        }
      })
      .finally(() => {
        setReviewing((prev) => {
          const next = new Set(prev)
          next.delete(nextId)
          return next
        })
        processingRef.current = false
        processNextRef.current()
      })
  }, [jobId, queryClient, handleCreditsExhausted])

  useEffect(() => {
    processNextRef.current = processNext
  }, [processNext])

  const enqueue = useCallback(
    (ids: string[]) => {
      const fresh = ids.filter((id) => !attemptedRef.current.has(id))
      if (fresh.length === 0) return
      fresh.forEach((id) => attemptedRef.current.add(id))
      queueRef.current.push(...fresh)
      setReviewing((prev) => {
        const next = new Set(prev)
        fresh.forEach((id) => next.add(id))
        return next
      })
      processNext()
    },
    [processNext],
  )

  useEffect(() => {
    if (creditsExhausted) return
    enqueue(items.filter(isEligible).map((item) => item.application_id))
  }, [items, isEligible, enqueue, creditsExhausted])

  const restart = useCallback(() => {
    setErrored(new Set())
    setCreditsExhausted(false)
    const retryable = items.filter(isEligible).map((item) => item.application_id)
    retryable.forEach((id) => attemptedRef.current.delete(id))
    enqueue(retryable)
  }, [items, isEligible, enqueue])

  return {
    reviewingIds: reviewing,
    erroredIds: errored,
    pendingCount: reviewing.size,
    creditsExhausted,
    restart,
  }
}
