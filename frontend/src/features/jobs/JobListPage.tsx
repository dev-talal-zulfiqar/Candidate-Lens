import type { MouseEvent } from 'react'
import { Link } from 'react-router'
import { useDeleteJobMutation, useJobsQuery } from './hooks'

export function JobListPage() {
  const jobsQuery = useJobsQuery()

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-12">
      <div className="flex items-end justify-between">
        <div>
          <p className="eyebrow">Pipelines</p>
          <h1 className="mt-1 text-4xl text-ink">Jobs</h1>
        </div>
        <Link to="/jobs/new" className="btn-primary">
          New job
        </Link>
      </div>

      <JobsList
        jobs={jobsQuery.data}
        isLoading={jobsQuery.isLoading}
        isError={jobsQuery.isError}
      />
    </div>
  )
}

function JobsList({
  jobs,
  isLoading,
  isError,
}: {
  jobs: { id: string; title: string; requirement_count: number }[] | undefined
  isLoading: boolean
  isError: boolean
}) {
  if (isLoading) {
    return (
      <ul className="flex flex-col gap-2" aria-busy="true">
        {[0, 1].map((key) => (
          <li key={key} className="card h-16 animate-pulse" />
        ))}
      </ul>
    )
  }

  if (isError) {
    return (
      <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
        Couldn't load jobs. Check that the backend is reachable and try again.
      </p>
    )
  }

  if (!jobs || jobs.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border-strong px-3 py-10 text-center text-sm text-ink-400">
        No jobs yet.{' '}
        <Link to="/jobs/new" className="text-terracotta underline">
          Create one
        </Link>{' '}
        to get started.
      </p>
    )
  }

  return (
    <ul className="flex flex-col gap-2">
      {jobs.map((job) => (
        <JobRow key={job.id} job={job} />
      ))}
    </ul>
  )
}

function JobRow({ job }: { job: { id: string; title: string; requirement_count: number } }) {
  const deleteJobMutation = useDeleteJobMutation()

  const handleDelete = (event: MouseEvent) => {
    event.preventDefault()
    event.stopPropagation()
    const confirmed = window.confirm(
      `Delete "${job.title}"? This removes all of its candidates, uploads, and evaluations. This can't be undone.`,
    )
    if (!confirmed) return
    deleteJobMutation.mutate(job.id)
  }

  return (
    <li className="card flex items-center justify-between px-5 py-4 transition-colors hover:border-border-strong hover:bg-cream-100">
      <Link to={`/jobs/${job.id}`} className="flex flex-1 items-center justify-between gap-4">
        <span className="font-display text-lg text-ink">{job.title}</span>
        <span className="eyebrow">
          {job.requirement_count}{' '}
          {job.requirement_count === 1 ? 'requirement' : 'requirements'}
        </span>
      </Link>
      <button
        type="button"
        onClick={handleDelete}
        disabled={deleteJobMutation.isPending}
        aria-label={`Delete ${job.title}`}
        className="ml-4 shrink-0 rounded-md border border-red-200 px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {deleteJobMutation.isPending ? 'Deleting…' : 'Delete'}
      </button>
    </li>
  )
}
