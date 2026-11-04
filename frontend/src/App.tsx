import { useEffect, useState } from 'react'
import { fetchHealth } from './api/client'

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

function StatusBadge({ state }: { state: ConnectionState }) {
  if (state.status === 'loading') {
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-600">
        <span className="h-2 w-2 animate-pulse rounded-full bg-slate-400" />
        Checking backend&hellip;
      </span>
    )
  }

  if (state.status === 'connected') {
    const dbOk = state.database === 'ok'
    return (
      <span
        className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium ${
          dbOk
            ? 'bg-emerald-100 text-emerald-800'
            : 'bg-amber-100 text-amber-800'
        }`}
      >
        <span
          className={`h-2 w-2 rounded-full ${dbOk ? 'bg-emerald-500' : 'bg-amber-500'}`}
        />
        Backend connected &middot; database {dbOk ? 'ok' : 'unavailable'}
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-red-100 px-3 py-1 text-sm font-medium text-red-800">
      <span className="h-2 w-2 rounded-full bg-red-500" />
      Backend unreachable
    </span>
  )
}

function App() {
  const health = useBackendHealth()

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-slate-900">
              CandidateLens
            </h1>
            <p className="text-sm text-slate-500">
              AI-assisted candidate evaluation workspace
            </p>
          </div>
          <StatusBadge state={health} />
        </div>
      </header>

      <main className="mx-auto flex max-w-5xl flex-1 flex-col items-start justify-center gap-4 px-6 py-16">
        <h2 className="text-2xl font-semibold text-slate-900">
          Application shell initialized
        </h2>
        <p className="max-w-xl text-slate-600">
          This is the foundation for CandidateLens. Job setup, resume upload,
          and candidate review workflows will be built on top of this shell in
          upcoming milestones.
        </p>
        {health.status === 'unreachable' && (
          <p className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
            Could not reach the backend at the configured API base URL (
            {health.message}). Confirm the backend is running and{' '}
            <code>VITE_API_BASE_URL</code> is set correctly.
          </p>
        )}
      </main>
    </div>
  )
}

export default App
