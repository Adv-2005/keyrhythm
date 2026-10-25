export type HealthResponse = { status: 'ok' }
import { CHALLENGE_VERSION, FEATURE_VERSION, type TimingSequence } from './timing'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${apiBaseUrl}/health`, { signal })
  if (!response.ok) {
    throw new Error(`Health request failed (${response.status})`)
  }

  const data: unknown = await response.json()
  if (!data || typeof data !== 'object' || !('status' in data) || data.status !== 'ok') {
    throw new Error('Unexpected health response')
  }
  return { status: 'ok' }
}

export type Profile = {
  id: number
  display_name: string
  created_at: string
  sample_count: number
  enrollment_target: number
  enrollment_status: 'collecting' | 'ready'
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => null) as { detail?: unknown } | null
    throw new Error(typeof detail?.detail === 'string' ? detail.detail : `Request failed (${response.status})`)
  }
  return response.status === 204 ? undefined as T : await response.json() as T
}

export const listProfiles = (signal?: AbortSignal) => apiRequest<Profile[]>('/profiles', { signal })
export const createProfile = (display_name: string) => apiRequest<Profile>('/profiles', {
  method: 'POST', body: JSON.stringify({ display_name }),
})
export const deleteProfile = (id: number) => apiRequest<void>(`/profiles/${id}`, { method: 'DELETE' })
export const submitSample = (id: number, session_id: string, timing_sequence: TimingSequence) =>
  apiRequest<{ id: number; profile_id: number; created_at: string; sample_count: number }>(`/profiles/${id}/samples`, {
    method: 'POST',
    body: JSON.stringify({ consent_acknowledged: true, session_id, challenge_version: CHALLENGE_VERSION, feature_version: FEATURE_VERSION, timing_sequence }),
  })

export type Calibration = {
  false_acceptance_rate: number
  false_rejection_rate: number
  genuine_count: number
  impostor_count: number
  session_disjoint: boolean
}

export type ModelStatus = {
  model_version: string
  minimum_samples_per_profile: number
  minimum_profiles: number
  eligible_profile_count: number
  profiles: {
    profile_id: number
    sample_count: number
    status: 'needs_data' | 'needs_training' | 'stale' | 'ready'
    training_count: number | null
    validation_count: number | null
    calibration: Calibration | null
  }[]
}

export type AuthenticationResult = {
  profile_id: number
  model_type: 'baseline' | 'siamese'
  similarity_score: number
  decision_threshold: number
  distance: number
  accepted: boolean
  model_version: string
  feature_matrix_version: string
  calibration: Calibration
  explanation: string
}

export const getModelStatus = (signal?: AbortSignal) => apiRequest<ModelStatus>('/models/status', { signal })
export const trainBaseline = () => apiRequest<unknown>('/models/train', { method: 'POST' })
export type SiameseProfile = {
  profile_id: number
  training_count: number
  validation_count: number
  held_out_count: number
  session_disjoint: boolean
  calibration: Calibration
}
export type LossEpoch = { epoch: number; train_loss: number; validation_loss: number }
export type SiameseStatus = {
  model_version: string
  status: 'needs_data' | 'needs_training' | 'stale' | 'ready'
  minimum_profiles: number
  minimum_samples_per_profile: number
  eligible_profile_count: number
  best_epoch: number | null
  history: LossEpoch[]
  profiles: SiameseProfile[]
}
export type SiameseTrainConfig = {
  epochs: number
  batch_size: number
  learning_rate: number
  embedding_dim: number
  margin: number
  seed: number
}
export const getSiameseStatus = (signal?: AbortSignal) => apiRequest<SiameseStatus>('/models/siamese/status', { signal })
export const trainSiamese = (config: SiameseTrainConfig) => apiRequest<unknown>('/models/siamese/train', {
  method: 'POST', body: JSON.stringify(config),
})
export const authenticate = (profile_id: number, session_id: string, timing_sequence: TimingSequence,
  model_type: 'baseline' | 'siamese' = 'baseline') =>
  apiRequest<AuthenticationResult>('/authenticate', {
    method: 'POST',
    body: JSON.stringify({
      profile_id,
      model_type,
      sample: { consent_acknowledged: true, session_id, challenge_version: CHALLENGE_VERSION,
        feature_version: FEATURE_VERSION, timing_sequence },
    }),
  })

export type EvaluationMetrics = {
  genuine_count: number
  impostor_count: number
  true_positive: number
  false_negative: number
  false_positive: number
  true_negative: number
  false_acceptance_rate: number
  false_rejection_rate: number
  precision: number | null
  recall: number
  roc_auc: number | null
  equal_error_rate: number | null
  auc_eer_supported: boolean
}

export type ExperimentSummary = {
  id: number
  created_at: string
  dataset_fingerprint: string
  protocol_version: string
  profile_count: number
  test_recording_count: number
  baseline: EvaluationMetrics
  siamese: EvaluationMetrics
}

export type Experiment = {
  id: number
  created_at: string
  result: {
    protocol_version: string
    dataset_fingerprint: string
    profile_count: number
    sample_count: number
    test_recording_count: number
    trial_count_per_model: number
    model_versions: Record<string, string>
    split_configuration: Record<string, { train_ids: number[]; validation_ids: number[]; test_ids: number[]; session_disjoint: boolean }>
    models: Record<'baseline' | 'siamese', { metrics: EvaluationMetrics }>
    reference_count_effect: { reference_count: number; baseline: EvaluationMetrics; siamese: EvaluationMetrics }[]
    limitations: string[]
  }
}

export const listExperiments = (signal?: AbortSignal) => apiRequest<ExperimentSummary[]>('/experiments', { signal })
export const getExperiment = (id: number, signal?: AbortSignal) => apiRequest<Experiment>(`/experiments/${id}`, { signal })
export const runEvaluation = () => apiRequest<Experiment>('/experiments/evaluate', { method: 'POST' })
export const experimentPlotUrl = (id: number, plot: 'roc' | 'confusion') =>
  `${apiBaseUrl}/experiments/${id}/plots/${plot}.svg`
