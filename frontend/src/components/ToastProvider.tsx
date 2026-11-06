import { useCallback, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { ToastContext } from './ToastContext'

interface Toast {
  id: number
  message: string
  variant: 'error' | 'info'
}

const AUTO_DISMISS_MS = 8000

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(0)

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const showToast = useCallback(
    (message: string, variant: Toast['variant'] = 'error') => {
      const id = nextId.current++
      setToasts((prev) => [...prev, { id, message, variant }])
      setTimeout(() => dismiss(id), AUTO_DISMISS_MS)
    },
    [dismiss],
  )

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex flex-col items-center gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="alert"
            className={`pointer-events-auto flex max-w-md items-start gap-3 rounded-lg border px-4 py-3 shadow-lg ${
              toast.variant === 'error'
                ? 'border-red-200 bg-red-50 text-red-800'
                : 'border-border-strong bg-paper text-ink'
            }`}
          >
            <p className="text-sm font-medium">{toast.message}</p>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss"
              className="shrink-0 text-xs text-current underline opacity-70 hover:opacity-100"
            >
              Dismiss
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
