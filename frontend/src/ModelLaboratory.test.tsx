import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import ModelLaboratory from './ModelLaboratory'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('shows real training history after a neural run and sends the selected parameters', async () => {
  let trained = false
  let body: string | undefined
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/models/status')) return { ok: true, status: 200, json: async () => ({
      model_version: 'baseline-distance-v1', minimum_profiles: 2,
      minimum_samples_per_profile: 6, eligible_profile_count: 3,
      profiles: [{ profile_id: 1, status: 'needs_training' }],
    }) }
    if (url.endsWith('/experiments')) return { ok: true, status: 200, json: async () => [] }
    if (url.endsWith('/models/siamese/status')) return { ok: true, status: 200, json: async () => ({
      model_version: 'siamese-cnn-v1', status: trained ? 'ready' : 'needs_training',
      minimum_profiles: 3, minimum_samples_per_profile: 10, eligible_profile_count: 3,
      best_epoch: trained ? 1 : null,
      history: trained ? [{ epoch: 1, train_loss: 0.31, validation_loss: 0.37 }] : [],
      profiles: trained ? [{ profile_id: 1, training_count: 6, validation_count: 2,
        held_out_count: 2, session_disjoint: true,
        calibration: { false_acceptance_rate: 0, false_rejection_rate: 0.5,
          genuine_count: 2, impostor_count: 4, session_disjoint: true } }] : [],
    }) }
    if (url.endsWith('/models/siamese/train')) {
      body = init?.body as string
      trained = true
      return { ok: true, status: 200, json: async () => ({ model_version: 'siamese-cnn-v1' }) }
    }
    throw new Error(`Unexpected URL ${url}`)
  }))

  render(<ModelLaboratory />)
  expect(await screen.findByText('needs training')).toBeTruthy()
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Epochs' }), { target: { value: '1' } })
  fireEvent.click(screen.getByRole('button', { name: 'Train Siamese model' }))
  expect(await screen.findByText(/Training complete/)).toBeTruthy()
  expect(screen.getByText('0.3700')).toBeTruthy()
  expect(screen.getByRole('figure', { name: 'Training and validation loss chart' })).toBeTruthy()
  expect(JSON.parse(body!).epochs).toBe(1)
})

it('fits the selected baseline and shows comparison values from a saved experiment', async () => {
  let trained = false
  const metrics = { false_acceptance_rate: 0.1, false_rejection_rate: 0.2,
    roc_auc: null, equal_error_rate: null }
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.endsWith('/models/status')) return { ok: true, status: 200, json: async () => ({
      model_version: 'baseline-distance-v1', minimum_profiles: 2, minimum_samples_per_profile: 6,
      eligible_profile_count: 2, profiles: [{ profile_id: 1, status: trained ? 'ready' : 'needs_training' }],
    }) }
    if (url.endsWith('/models/siamese/status')) return { ok: true, status: 200, json: async () => ({
      model_version: 'siamese-cnn-v1', status: 'ready', minimum_profiles: 3,
      minimum_samples_per_profile: 10, eligible_profile_count: 3,
      best_epoch: 1, history: [], profiles: [],
    }) }
    if (url.endsWith('/experiments')) return { ok: true, status: 200, json: async () => [{
      id: 9, created_at: '2026-10-25T00:00:00Z', test_recording_count: 9,
      baseline: metrics, siamese: { ...metrics, false_acceptance_rate: 0.3 },
    }] }
    if (url.endsWith('/models/train')) {
      trained = true
      return { ok: true, status: 200, json: async () => ({}) }
    }
    throw new Error(`Unexpected URL ${url}`)
  }))

  render(<ModelLaboratory />)
  expect(await screen.findByText(/Experiment #9/)).toBeTruthy()
  expect(screen.getByText('10.0%')).toBeTruthy()
  expect(screen.getByText('30.0%')).toBeTruthy()
  fireEvent.change(screen.getByRole('combobox', { name: 'Model' }), { target: { value: 'baseline' } })
  fireEvent.click(screen.getByRole('button', { name: 'Train baseline' }))
  expect(await screen.findByText(/Training complete/)).toBeTruthy()
  expect(trained).toBe(true)
})
