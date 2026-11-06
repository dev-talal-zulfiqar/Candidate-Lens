/** Deterministic banding of our own computed score into a plain-language
 * label — not an AI claim, just a presentation of the number we already
 * show numerically right next to it. */
export function fitQualityLabel(score: number): string {
  if (score >= 85) return 'Strong fit'
  if (score >= 65) return 'Good fit'
  if (score >= 40) return 'Possible fit'
  return 'Weak fit'
}
