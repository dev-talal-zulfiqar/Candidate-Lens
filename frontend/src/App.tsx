import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router'
import { fetchHealth } from './api/client'
import { ToastProvider } from './components/ToastProvider'
import { CandidateApplicationPage } from './features/candidates/CandidateApplicationPage'
import { CreateJobPage } from './features/jobs/CreateJobPage'
import { JobDetailPage } from './features/jobs/JobDetailPage'
import { JobListPage } from './features/jobs/JobListPage'

const queryClient = new QueryClient()

type ConnectionState =
  | { status: 'loading' }
  | { status: 'connected'; database: 'ok' | 'error' }
  | { status: 'unreachable'; message: string }

function useBackendHealth(): ConnectionState {
  const [state, setState] = useState<ConnectionState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false

    fetchHealth()
      .then((health) => {
        if (!cancelled) {
          setState({ status: 'connected', database: health.database })
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          const message =
            error instanceof Error ? error.message : 'Unknown error'
          setState({ status: 'unreachable', message })
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  return state
}

function AppShell() {
  const health = useBackendHealth()

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <span className="font-display text-2xl text-ink">
            Candidate <span className="text-terracotta">Lens</span>
          </span>
        </div>
      </header>

      {health.status === 'unreachable' && (
        <div className="mx-auto w-full max-w-6xl px-6 pt-4">
          <p role="alert" className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
            Could not reach the backend at the configured API base URL (
            {health.message}). Confirm the backend is running and{' '}
            <code>VITE_API_BASE_URL</code> is set correctly.
          </p>
        </div>
      )}

      <main className="flex-1">
        <Routes>
          <Route path="/" element={<JobListPage />} />
          <Route path="/jobs/new" element={<CreateJobPage />} />
          <Route path="/jobs/:jobId" element={<JobDetailPage />} />
          <Route
            path="/jobs/:jobId/candidates/:applicationId"
            element={<CandidateApplicationPage />}
          />
        </Routes>
      </main>
    </div>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <AppShell />
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  )
}

export default App
