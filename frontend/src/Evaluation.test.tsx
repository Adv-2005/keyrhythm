import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import Evaluation from './Evaluation'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('shows saved held-out metrics and omits unsupported AUC and EER claims', async () => {
  const metrics = {
    genuine_count: 9, impostor_count: 18,
    true_positive: 8, false_negative: 1, false_positive: 2, true_negative: 16,
    false_acceptance_rate: 2 / 18, false_rejection_rate: 1 / 9,
    precision: 0.8, recall: 8 / 9, roc_auc: null, equal_error_rate: null,
    auc_eer_supported: false,
  }
  let runs = 0
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.endsWith('/experiments')) return { ok: true, status: 200, json: async () => [] }
    if (url.endsWith('/experiments/evaluate')) {
      runs += 1
      return { ok: true, status: 200, json: async () => ({
        id: 7, created_at: '2026-10-25T00:00:00Z', result: {
          protocol_version: 'known-user-test-v1', dataset_fingerprint: 'abc123456789',
          profile_count: 3, sample_count: 30, test_recording_count: 9,
          trial_count_per_model: 27,
          model_versions: { baseline: 'baseline-distance-v1', siamese: 'siamese-cnn-v1' },
          split_configuration: { '1': { train_ids: [1], validation_ids: [2], test_ids: [3], session_disjoint: true } },
          models: { baseline: { metrics }, siamese: { metrics: { ...metrics, false_positive: 1, false_acceptance_rate: 1 / 18 } } },
          reference_count_effect: [{ reference_count: 2, baseline: metrics, siamese: metrics }],
          limitations: ['ROC-AUC and EER are omitted for this small test set.'],
        },
      }) }
    }
    throw new Error(`Unexpected URL ${url}`)
  }))

  render(<Evaluation />)
  fireEvent.click(screen.getByRole('button', { name: 'Run evaluation' }))
  expect(await screen.findByText('Held-out model comparison')).toBeTruthy()
  expect(screen.getAllByText('Insufficient attempts').length).toBe(4)
  expect(screen.getByText(/FAR uses 18 impostor attempts/)).toBeTruthy()
  expect(screen.getByRole('img', { name: 'ROC curves for baseline and Siamese verifier' }).getAttribute('src')).toContain('/experiments/7/plots/roc.svg')
  expect(runs).toBe(1)
})
