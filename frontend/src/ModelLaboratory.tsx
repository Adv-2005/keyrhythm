import { useEffect, useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getModelStatus, getSiameseStatus, listExperiments, runEvaluation, trainBaseline, trainSiamese,
  type ExperimentSummary, type ModelStatus, type SiameseStatus } from './api'

const percent = (value: number) => `${(value * 100).toFixed(1)}%`

export default function ModelLaboratory({ onNavigate }: { onNavigate?: (section: 'evaluation') => void }) {
  const [modelType, setModelType] = useState<'baseline' | 'siamese'>('siamese')
  const [baseline, setBaseline] = useState<ModelStatus | null>(null)
  const [status, setStatus] = useState<SiameseStatus | null>(null)
  const [latest, setLatest] = useState<ExperimentSummary | null>(null)
  const [epochs, setEpochs] = useState(20)
  const [embeddingDim, setEmbeddingDim] = useState(32)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([getModelStatus(controller.signal), getSiameseStatus(controller.signal), listExperiments(controller.signal)])
      .then(([baselineStatus, neuralStatus, experiments]) => {
        setBaseline(baselineStatus)
        setStatus(neuralStatus)
        setLatest(experiments[0] ?? null)
      })
      .catch(() => { if (!controller.signal.aborted) setError('Could not load model state. Check the API connection.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [])

  async function train() {
    setBusy(true)
    setError('')
    setMessage(modelType === 'siamese' ? 'Training the Siamese model on the current enrolment snapshot…' : 'Fitting the baseline on the current enrolment snapshot…')
    try {
      if (modelType === 'siamese') {
        await trainSiamese({ epochs, batch_size: 32, learning_rate: 0.001, embedding_dim: embeddingDim, margin: 1, seed: 42 })
        setStatus(await getSiameseStatus())
      } else {
        await trainBaseline()
        setBaseline(await getModelStatus())
      }
      setMessage('Training complete. Validation calibration is preliminary; run the held-out comparison for test results.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Training failed; no new model was saved.')
      setMessage('')
    } finally { setBusy(false) }
  }

  async function evaluate() {
    setBusy(true)
    setError('')
    setMessage('Evaluating the saved model on held-out recordings…')
    try {
      const result = await runEvaluation()
      const experiments = await listExperiments()
      setLatest(experiments.find((item) => item.id === result.id) ?? experiments[0] ?? null)
      setMessage('Evaluation saved. Open Evaluation for plots, denominators, and limitations.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Evaluation failed.')
      setMessage('')
    } finally { setBusy(false) }
  }

  const readyBaseline = baseline?.profiles.filter((profile) => profile.status === 'ready').length ?? 0
  const canTrain = modelType === 'siamese'
    ? !!status && status.eligible_profile_count >= status.minimum_profiles && Number.isInteger(epochs) && epochs >= 1 && epochs <= 100 && Number.isInteger(embeddingDim) && embeddingDim >= 4 && embeddingDim <= 256
    : !!baseline && baseline.eligible_profile_count >= baseline.minimum_profiles

  return <div className="space-y-6">
    <div className="grid gap-6 xl:grid-cols-[20rem_1fr]">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" aria-labelledby="lab-controls">
        <h2 id="lab-controls" className="text-lg font-semibold">Model laboratory</h2>
        <p className="mt-3 text-sm leading-6 text-slate-600">Fit the distance baseline or a shared Siamese encoder, then compare both on saved held-out recordings.</p>
        {loading && <p role="status" className="mt-4 text-sm text-slate-600">Loading model state…</p>}
        {error && <p role="alert" className="mt-4 text-sm text-rose-700">{error}</p>}
        <label htmlFor="lab-model" className="mt-5 block text-sm font-medium">Model</label>
        <select id="lab-model" value={modelType} disabled={busy} onChange={(event) => { setModelType(event.target.value as 'baseline' | 'siamese'); setMessage(''); setError('') }} className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2">
          <option value="siamese">Siamese CNN</option><option value="baseline">Distance baseline</option>
        </select>
        {modelType === 'siamese' ? <>
          {status && <p className="mt-4 text-sm text-slate-700">Status: <strong>{status.status.replace('_', ' ')}</strong>. {status.eligible_profile_count} of {status.minimum_profiles} required profiles have at least {status.minimum_samples_per_profile} samples.</p>}
          <label htmlFor="lab-epochs" className="mt-5 block text-sm font-medium">Epochs</label>
          <input id="lab-epochs" type="number" min="1" max="100" value={epochs} disabled={busy} onChange={(event) => setEpochs(Number(event.target.value))} className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2" />
          <label htmlFor="lab-embedding" className="mt-4 block text-sm font-medium">Embedding dimensions</label>
          <input id="lab-embedding" type="number" min="4" max="256" value={embeddingDim} disabled={busy} onChange={(event) => setEmbeddingDim(Number(event.target.value))} className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2" />
        </> : baseline && <p className="mt-4 text-sm text-slate-700">{readyBaseline} profiles ready. {baseline.eligible_profile_count} of {baseline.minimum_profiles} required profiles have at least {baseline.minimum_samples_per_profile} samples. Model {baseline.model_version}.</p>}
        <button type="button" onClick={train} disabled={busy || !canTrain} className="mt-5 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? 'Working…' : modelType === 'siamese' ? 'Train Siamese model' : 'Train baseline'}</button>
        <button type="button" onClick={evaluate} disabled={busy || status?.status !== 'ready'} className="mt-3 w-full rounded-lg border border-indigo-300 px-4 py-2 text-sm font-semibold text-indigo-700 disabled:opacity-50">Run held-out comparison</button>
        {message && <p role="status" className="mt-4 text-sm leading-6 text-slate-700">{message}</p>}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8" aria-labelledby="lab-results">
        <h2 id="lab-results" className="text-xl font-semibold">Training results</h2>
        {status?.status === 'ready' ? <>
          <p className="mt-3 text-sm text-slate-600">{status.model_version} · best validation epoch {status.best_epoch}. Loss and calibration are computed from training and validation data.</p>
          {status.history.length > 0 && <figure className="mt-6" aria-label="Training and validation loss chart">
            <figcaption className="mb-2 text-sm font-semibold">Loss by epoch</figcaption>
            <div className="h-56 w-full"><ResponsiveContainer width="100%" height="100%"><LineChart data={status.history} margin={{ top: 5, right: 12, left: 0, bottom: 5 }}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="epoch" /><YAxis domain={['auto', 'auto']} /><Tooltip /><Legend /><Line type="monotone" dataKey="train_loss" name="Training loss" stroke="#4f46e5" dot={false} /><Line type="monotone" dataKey="validation_loss" name="Validation loss" stroke="#e11d48" dot={false} /></LineChart></ResponsiveContainer></div>
          </figure>}
          <div className="mt-6 overflow-x-auto"><table className="w-full text-left text-sm"><caption className="mb-2 text-left font-semibold">Loss values by epoch</caption><thead><tr className="border-b border-slate-200"><th className="py-2">Epoch</th><th>Training loss</th><th>Validation loss</th></tr></thead><tbody>{status.history.map((item) => <tr key={item.epoch} className="border-b border-slate-100"><td className="py-2">{item.epoch}</td><td>{item.train_loss.toFixed(4)}</td><td>{item.validation_loss.toFixed(4)}</td></tr>)}</tbody></table></div>
          <h3 className="mt-7 font-semibold">Validation calibration</h3>
          <p className="mt-2 text-sm text-slate-600">These rates choose thresholds. Held-out recordings are reserved for the final experiment.</p>
          <ul className="mt-3 space-y-3">{status.profiles.map((profile) => <li key={profile.profile_id} className="rounded-lg bg-slate-50 p-3 text-sm">Profile {profile.profile_id}: {profile.training_count} train, {profile.validation_count} validation, {profile.held_out_count} held out · FAR {percent(profile.calibration.false_acceptance_rate)} · FRR {percent(profile.calibration.false_rejection_rate)} {profile.session_disjoint ? '· sessions separate' : '· sessions may overlap'}</li>)}</ul>
        </> : !loading && <p className="mt-4 text-sm leading-6 text-slate-600">Collect consenting samples from multiple profiles, then train to inspect real loss and calibration results.</p>}
      </section>
    </div>

    <section aria-labelledby="lab-comparison" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3"><h2 id="lab-comparison" className="text-xl font-semibold">Saved model comparison</h2>{onNavigate && <button type="button" onClick={() => onNavigate('evaluation')} className="text-sm font-medium text-indigo-700">Open Evaluation</button>}</div>
      {latest ? <><p className="mt-3 text-sm text-slate-600">Experiment #{latest.id} · {new Date(latest.created_at).toLocaleString()} · {latest.test_recording_count} held-out recordings. Results belong to that saved dataset snapshot.</p><div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b border-slate-200"><th className="py-2">Model</th><th>FAR</th><th>FRR</th><th>ROC-AUC</th><th>EER</th></tr></thead><tbody>{(['baseline', 'siamese'] as const).map((model) => <tr key={model} className="border-b border-slate-100"><th scope="row" className="py-2 font-medium">{model === 'baseline' ? 'Distance baseline' : 'Siamese CNN'}</th><td>{percent(latest[model].false_acceptance_rate)}</td><td>{percent(latest[model].false_rejection_rate)}</td><td>{latest[model].roc_auc === null ? 'Insufficient attempts' : latest[model].roc_auc?.toFixed(3)}</td><td>{latest[model].equal_error_rate === null ? 'Insufficient attempts' : percent(latest[model].equal_error_rate)}</td></tr>)}</tbody></table></div></> : !loading && <p className="mt-4 text-sm text-slate-600">No saved comparison yet. Train the Siamese model, then run the held-out comparison.</p>}
    </section>
  </div>
}
