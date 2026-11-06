export type RequirementCategory = 'mandatory' | 'preferred'

export interface JobRequirement {
  id: string
  job_id: string
  description: string
  category: RequirementCategory
  weight: string
  sort_order: number
  created_at: string
}

export interface Job {
  id: string
  title: string
  description_md: string
  rubric_version: number
  created_at: string
  updated_at: string
  requirements: JobRequirement[]
}

export interface JobSummary {
  id: string
  title: string
  rubric_version: number
  created_at: string
  requirement_count: number
}

export interface JobRequirementInput {
  description: string
  category: RequirementCategory
  weight: number
}

export interface JobCreateInput {
  title: string
  description_md: string
}

export interface RequirementSuggestion {
  description: string
  category: RequirementCategory
  weight: string
}
