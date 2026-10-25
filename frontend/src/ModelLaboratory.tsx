import { useEffect, useState } from 'react'
import { getSiameseStatus, trainSiamese, type SiameseStatus } from './api'

export default function ModelLaboratory() {
  const [status, setStatus] = useState<SiameseStatus | null>(null)
  const [epochs, setEpochs] = useState(20)
  const [embeddingDim, setEmbeddingDim] = useState(32)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    getSiameseStatus(controller.signal).then(setStatus).catch(() => {
      if (!controller.signal.aborted) setMessage('Could not load neural model status. Check the API connection.')
    })
    return () => controller.abort()
  }, [])

  async function train() {
    setBusy(true)
    setMessage('Training the Siamese model on the current enrollment snapshot…')
    try {
      await trainSiamese({ epochs, batch_size: 32, learning_rate: 0.001, embedding_dim: embeddingDim, margin: 1, seed: 42 })
      setStatus(await getSiameseStatus())
      setMessage('Training complete. Validation results are preliminary; held-out evaluation is planned for Milestone 5.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Neural training failed; no new model was saved.')
    } finally { setBusy(false) }
  }

  return <div className="grid gap-6 xl:grid-cols-[20rem_1fr]">
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" aria-labelledby="lab-controls">
      <h2 id="lab-controls" className="text-lg font-semibold">Siamese CNN</h2>
      <p className="mt-3 text-sm leading-6 text-slate-600">Train a shared encoder on balanced genuine and impostor timing pairs. This local CPU run uses validation samples for checkpoint selection and threshold calibration.</p>
      {status && <p className="mt-4 text-sm text-slate-700">Status: <strong>{status.status.replace('_', ' ')}</strong>. {status.eligible_profile_count} of {status.minimum_profiles} required profiles have at least {status.minimum_samples_per_profile} samples.</p>}
      <label htmlFor="lab-epochs" className="mt-5 block text-sm font-medium">Epochs</label>
      <input id="lab-epochs" type="number" min="1" max="100" value={epochs} disabled={busy}
        onChange={(event) => setEpochs(Number(event.target.value))}
        className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2" />
      <label htmlFor="lab-embedding" className="mt-4 block text-sm font-medium">Embedding dimensions</label>
      <input id="lab-embedding" type="number" min="4" max="256" value={embeddingDim} disabled={busy}
        onChange={(event) => setEmbeddingDim(Number(event.target.value))}
        className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2" />
      <button type="button" onClick={train}
        disabled={busy || !status || status.eligible_profile_count < status.minimum_profiles || !Number.isInteger(epochs) || epochs < 1 || epochs > 100 || !Number.isInteger(embeddingDim) || embeddingDim < 4 || embeddingDim > 256}
        className="mt-5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? 'Training…' : 'Train Siamese model'}</button>
      {message && <p role="status" className="mt-4 text-sm leading-6 text-slate-700">{message}</p>}
    </section>

    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8" aria-labelledby="lab-results">
      <h2 id="lab-results" className="text-xl font-semibold">Training results</h2>
      {status?.status === 'ready' ? <>
        <p className="mt-3 text-sm text-slate-600">{status.model_version} · best validation epoch {status.best_epoch}. Similarities are not probabilities.</p>
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="mb-2 text-left font-semibold">Loss by epoch</caption>
            <thead><tr className="border-b border-slate-200"><th className="py-2">Epoch</th><th>Training loss</th><th>Validation loss</th></tr></thead>
            <tbody>{status.history.map((item) => <tr key={item.epoch} className="border-b border-slate-100"><td className="py-2">{item.epoch}</td><td>{item.train_loss.toFixed(4)}</td><td>{item.validation_loss.toFixed(4)}</td></tr>)}</tbody>
          </table>
        </div>
        <h3 className="mt-7 font-semibold">Validation calibration</h3>
        <p className="mt-2 text-sm text-slate-600">These rates come from validation recordings used to choose thresholds. Held-out samples are reserved for the final experiment.</p>
        <ul className="mt-3 space-y-3">{status.profiles.map((profile) => <li key={profile.profile_id} className="rounded-lg bg-slate-50 p-3 text-sm">
          Profile {profile.profile_id}: {profile.training_count} train, {profile.validation_count} validation, {profile.held_out_count} held out · FAR {(profile.calibration.false_acceptance_rate * 100).toFixed(1)}% · FRR {(profile.calibration.false_rejection_rate * 100).toFixed(1)}% {profile.session_disjoint ? '· sessions separate' : '· sessions may overlap'}
        </li>)}</ul>
      </> : <p className="mt-4 text-sm leading-6 text-slate-600">Collect consenting samples from multiple profiles, then train to inspect real loss and calibration results.</p>}
    </section>
  </div>
}
