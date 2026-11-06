import { Link, useNavigate } from 'react-router'
import { CreateJobForm } from './components/CreateJobForm'

export function CreateJobPage() {
  const navigate = useNavigate()

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-12">
      <div>
        <Link to="/" className="eyebrow normal-case hover:text-ink-600">
          ← All jobs
        </Link>
        <p className="eyebrow mt-4">New pipeline</p>
        <h1 className="mt-1 text-4xl text-ink">Create a job</h1>
        <p className="mt-2 text-sm text-ink-600">
          Paste or write the job description, then set up its requirements
          on the next screen.
        </p>
      </div>

      <div className="card p-6">
        <CreateJobForm onCreated={(jobId) => navigate(`/jobs/${jobId}`)} />
      </div>
    </div>
  )
}
