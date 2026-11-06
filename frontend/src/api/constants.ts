// Must match app.integrations.ai_provider.AI_CREDITS_EXHAUSTED_MESSAGE on the
// backend exactly — the frontend matches on this literal string (in an
// evaluation's error_message, or an ApiError's message on a 402 response)
// to decide when to show the "contact your admin" toast instead of a
// generic retryable error.
export const AI_CREDITS_EXHAUSTED_MESSAGE = 'AI credits exhausted — contact your admin.'
