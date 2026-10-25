import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import Overview from './Overview'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('shows counts, model state, and saved metrics returned by the API', async () => {
  const navigate = vi.fn()
  const metrics = {
    false_acceptance_rate: 0.125, false_rejection_rate: 0.25,
    roc_auc: 0.812, equal_error_rate: 0.2,
  }
  vi.stubGlobal('fetch', vi.fn(async (url: string) => ({
    ok: true, status: 200,
    json: async () => url.endsWith('/profiles') ? [
      { id: 1, sample_count: 6 }, { id: 2, sample_count: 7 },
    ] : url.endsWith('/models/status') ? {
      model_version: 'baseline-distance-v1', profiles: [
        { profile_id: 1, status: 'ready' }, { profile_id: 2, status: 'stale' },
      ],
    } : url.endsWith('/models/siamese/status') ? {
      model_version: 'siamese-cnn-v1', status: 'stale',
    } : [{ id: 4, created_at: '2026-10-25T00:00:00Z', test_recording_count: 9,
      baseline: metrics, siamese: { ...metrics, false_acceptance_rate: 0.375 } }],
  })))

  render(<Overview onNavigate={navigate} />)
  expect(await screen.findByText('13')).toBeTruthy()
  expect(screen.getByText('1 / 2')).toBeTruthy()
  expect(screen.getByText('Run #4', { exact: false })).toBeTruthy()
  expect(screen.getByText(/FAR 12.5%/)).toBeTruthy()
  expect(screen.getByText(/FAR 37.5%/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Verify a sample' }))
  expect(navigate).toHaveBeenCalledWith('authentication')
})
