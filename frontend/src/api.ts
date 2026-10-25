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
export const authenticate = (profile_id: number, session_id: string, timing_sequence: TimingSequence) =>
  apiRequest<AuthenticationResult>('/authenticate', {
    method: 'POST',
    body: JSON.stringify({
      profile_id,
      sample: { consent_acknowledged: true, session_id, challenge_version: CHALLENGE_VERSION,
        feature_version: FEATURE_VERSION, timing_sequence },
    }),
  })
