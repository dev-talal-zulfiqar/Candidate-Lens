import { createContext } from 'react'

export interface ToastContextValue {
  showToast: (message: string, variant?: 'error' | 'info') => void
}

export const ToastContext = createContext<ToastContextValue | null>(null)
