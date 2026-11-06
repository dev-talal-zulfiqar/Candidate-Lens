interface ReviewingBannerProps {
  pendingCount: number
  onRestart: () => void
}

export function ReviewingBanner({ pendingCount, onRestart }: ReviewingBannerProps) {
  if (pendingCount === 0) return null

  return (
    <div className="flex items-center justify-between rounded-md border border-terracotta-100 bg-terracotta-50 px-4 py-2.5">
      <span className="eyebrow text-terracotta-600 normal-case">
        Reviewing {pendingCount} resume{pendingCount === 1 ? '' : 's'} — keep this page open
      </span>
      <button
        type="button"
        onClick={onRestart}
        className="eyebrow text-ink-600 underline hover:text-ink"
      >
        Restart queue
      </button>
    </div>
  )
}
