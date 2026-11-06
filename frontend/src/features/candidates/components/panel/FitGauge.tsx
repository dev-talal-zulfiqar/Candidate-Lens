interface FitGaugeProps {
  score: number
}

export function FitGauge({ score }: FitGaugeProps) {
  const pct = Math.max(0, Math.min(100, score))

  return (
    <div
      role="img"
      aria-label={`Fit score ${Math.round(score)} out of 100`}
      className="relative flex h-28 w-28 shrink-0 items-center justify-center rounded-full"
      style={{
        background: `conic-gradient(var(--color-terracotta) ${pct}%, var(--color-cream-200) ${pct}% 100%)`,
      }}
    >
      <div className="flex h-[88px] w-[88px] flex-col items-center justify-center rounded-full bg-paper">
        <span className="font-display text-2xl text-ink">{Math.round(score)}</span>
        <span className="eyebrow">/100 fit</span>
      </div>
    </div>
  )
}
