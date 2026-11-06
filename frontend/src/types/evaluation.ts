export type EvaluationStage = 'preliminary' | 'ai'
export type EvaluationRunStatus = 'pending' | 'running' | 'completed' | 'failed'
export type RequirementCategory = 'mandatory' | 'preferred'
export type RequirementResultStatus = 'met' | 'not_met' | 'unverified'

export interface EvidenceQuote {
  quote?: string
  term?: string
}

export interface RequirementResult {
  id: string
  requirement_id: string
  requirement_description: string
  requirement_category: RequirementCategory
  status: RequirementResultStatus
  evidence_json: EvidenceQuote[]
  explanation: string
}

export interface Strength {
  description: string
  evidence_quote: string
}

export interface Evaluation {
  id: string
  application_id: string
  rubric_version: number
  stage: EvaluationStage
  status: EvaluationRunStatus
  score: string | null
  coverage_score: string | null
  model_version: string | null
  prompt_version: string | null
  strengths_json: Strength[]
  questions_json: string[]
  error_message: string | null
  created_at: string
  completed_at: string | null
  requirement_results: RequirementResult[]
}
