import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import Authentication from './Authentication'
import { CHALLENGE } from './timing'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('trains the baseline and displays the returned verification decision', async () => {
  let trained = false
  let authenticationBody: string | undefined
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/profiles')) {
      return { ok: true, status: 200, json: async () => [
        { id: 1, display_name: 'P1', sample_count: 10, enrollment_target: 10, enrollment_status: 'ready' },
        { id: 2, display_name: 'P2', sample_count: 10, enrollment_target: 10, enrollment_status: 'ready' },
      ] }
    }
    if (url.endsWith('/models/status')) {
      return { ok: true, status: 200, json: async () => ({
        model_version: 'baseline-distance-v1', minimum_samples_per_profile: 6,
        minimum_profiles: 2, eligible_profile_count: 2,
        profiles: [1, 2].map((id) => ({ profile_id: id, sample_count: 10,
          status: trained ? 'ready' : 'needs_training', training_count: trained ? 8 : null,
          validation_count: trained ? 2 : null, calibration: null })),
      }) }
    }
    if (url.endsWith('/models/train')) {
      trained = true
      return { ok: true, status: 200, json: async () => ({ model_version: 'baseline-distance-v1' }) }
    }
    if (url.endsWith('/authenticate')) {
      authenticationBody = init?.body as string
      return { ok: true, status: 200, json: async () => ({
        profile_id: 1, similarity_score: 0.872, decision_threshold: 0.7,
        distance: 0.1468, accepted: true, model_version: 'baseline-distance-v1',
        feature_matrix_version: 'baseline-features-v1',
        calibration: { false_acceptance_rate: 0, false_rejection_rate: 0,
          genuine_count: 2, impostor_count: 2, session_disjoint: true },
        explanation: 'Normalized typing timing is within the validation-calibrated baseline threshold.',
      }) }
    }
    throw new Error(`Unexpected URL ${url}`)
  }))

  render(<Authentication />)
  expect(await screen.findByText('Model: needs training')).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Verify sample' }).hasAttribute('disabled')).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: 'Train baseline' }))
  expect(await screen.findByText('Model: ready')).toBeTruthy()
  fireEvent.click(screen.getByRole('checkbox'))
  const input = screen.getByRole('textbox', { name: 'Type the sentence exactly' })
  let typed = ''
  for (let i = 0; i < CHALLENGE.length; i++) {
    const key = CHALLENGE[i]
    const code = `pos-${i}`
    const down = new KeyboardEvent('keydown', { bubbles: true, key, code })
    Object.defineProperty(down, 'timeStamp', { value: 100 + i * 150 })
    fireEvent(input, down)
    typed += key
    fireEvent.change(input, { target: { value: typed } })
    const up = new KeyboardEvent('keyup', { bubbles: true, key, code })
    Object.defineProperty(up, 'timeStamp', { value: 180 + i * 150 })
    fireEvent(input, up)
  }
  fireEvent.click(screen.getByRole('button', { name: 'Verify sample' }))
  expect(await screen.findByRole('heading', { name: 'Accepted by baseline' })).toBeTruthy()
  expect(screen.getByText(/Similarity 0.872 · threshold 0.700/)).toBeTruthy()
  await waitFor(() => expect(authenticationBody).toBeDefined())
  const sent = JSON.parse(authenticationBody!)
  expect(sent.profile_id).toBe(1)
  expect(sent.sample.timing_sequence.hold_ms).toHaveLength(CHALLENGE.length)
  expect(JSON.stringify(sent)).not.toContain(CHALLENGE)
})
