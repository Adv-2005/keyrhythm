import { useEffect, useState } from 'react'
import { authenticate, getModelStatus, getSiameseStatus, listProfiles, listTrials, trainBaseline,
  type AuthenticationResult, type ModelStatus, type Profile, type SiameseStatus, type VerificationTrial } from './api'
import ChallengeCapture from './ChallengeCapture'
import type { TimingSequence } from './timing'

export default function Authentication() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [status, setStatus] = useState<ModelStatus | null>(null)
  const [neuralStatus, setNeuralStatus] = useState<SiameseStatus | null>(null)
  const [modelType, setModelType] = useState<'baseline' | 'siamese'>('baseline')
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [trials, setTrials] = useState<VerificationTrial[]>([])
  const [result, setResult] = useState<AuthenticationResult | null>(null)
  const [sessionId] = useState(() => crypto.randomUUID())
  const selected = profiles.find((profile) => profile.id === selectedId)
  const model = status?.profiles.find((item) => item.profile_id === selectedId)
  const neuralReady = neuralStatus?.status === 'ready' && neuralStatus.profiles.some((item) => item.profile_id === selectedId)
  const ready = modelType === 'baseline' ? model?.status === 'ready' : neuralReady

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([listProfiles(controller.signal), getModelStatus(controller.signal), getSiameseStatus(controller.signal), listTrials(controller.signal)])
      .then(([items, modelStatus, siamese, recentTrials]) => {
        setProfiles(items)
        setSelectedId(items[0]?.id ?? null)
        setStatus(modelStatus)
        setNeuralStatus(siamese)
        setTrials(recentTrials)
      })
      .catch(() => { if (!controller.signal.aborted) setError('Could not load profiles or model status. Check the API connection.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [])

  async function train() {
    setBusy(true)
    setResult(null)
    setError('')
    try {
      await trainBaseline()
      setStatus(await getModelStatus())
      setMessage('Baseline fitted and calibrated on the current enrollment samples.')
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Could not train the baseline.')
    } finally { setBusy(false) }
  }

  async function verify(sequence: TimingSequence): Promise<string> {
    if (!selected || !consent) throw new Error('Select a profile and consent before verification.')
    setBusy(true)
    setResult(null)
    setError('')
    setMessage('Verifying timing against the selected profile…')
    try {
      const verification = await authenticate(selected.id, sessionId, sequence, modelType)
      setResult(verification)
      const recentTrials = await listTrials().catch(() => null)
      if (recentTrials) setTrials(recentTrials)
      setMessage('Verification complete. Result shown below.')
      return 'Verification complete. This result is experimental.'
    } catch (error) {
      setMessage('')
      if (error instanceof Error && error.message.includes('retrain')) {
        if (modelType === 'baseline') {
          const latest = await getModelStatus().catch(() => null)
          if (latest) setStatus(latest)
        } else {
          const latest = await getSiameseStatus().catch(() => null)
          if (latest) setNeuralStatus(latest)
        }
      }
      throw error
    } finally { setBusy(false) }
  }

  return <div className="space-y-6"><div className="grid gap-6 xl:grid-cols-[18rem_1fr]">
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" aria-labelledby="verification-profile-heading">
      <h2 id="verification-profile-heading" className="text-lg font-semibold">Verification model</h2>
      {loading && <p role="status" className="mt-3 text-sm text-slate-600">Loading profiles and model status…</p>}
      {error && <p role="alert" className="mt-3 text-sm text-rose-700">{error}</p>}
      {!loading && profiles.length === 0 && !error && <p className="mt-3 text-sm text-slate-600">No profiles yet. Create a profile in Enrolment first.</p>}
      <label htmlFor="verification-model" className="mt-5 block text-sm font-medium">Model</label>
      <select id="verification-model" value={modelType} disabled={busy}
        onChange={(event) => { setModelType(event.target.value as 'baseline' | 'siamese'); setResult(null); setConsent(false); setMessage('') }}
        className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2">
        <option value="baseline">Distance baseline</option><option value="siamese">Siamese CNN</option>
      </select>
      <label htmlFor="verification-profile" className="mt-5 block text-sm font-medium">Selected profile</label>
      <select id="verification-profile" value={selectedId ?? ''} disabled={busy || profiles.length === 0}
        onChange={(event) => { setSelectedId(Number(event.target.value)); setConsent(false); setResult(null); setMessage('') }}
        className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2">
        {profiles.length === 0 && <option value="">No profiles yet</option>}
        {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.display_name}</option>)}
      </select>
      {selected && <p className="mt-4 text-sm text-slate-600">{selected.sample_count} enrollment samples</p>}
      {modelType === 'baseline' && status && <>
        <p className="mt-3 text-sm text-slate-600">Model: {model?.status.replace('_', ' ') ?? 'unavailable'}</p>
        <p className="mt-3 text-sm leading-6 text-slate-600">Training needs {status.minimum_profiles} profiles with at least {status.minimum_samples_per_profile} samples each. {status.eligible_profile_count} currently qualify.</p>
        <button type="button" onClick={train} disabled={busy || status.eligible_profile_count < status.minimum_profiles}
          className="mt-5 rounded-lg border border-indigo-300 px-4 py-2 text-sm font-semibold text-indigo-700 disabled:opacity-50">Train baseline</button>
      </>}
      {modelType === 'siamese' && neuralStatus && <>
        <p className="mt-3 text-sm text-slate-600">Model: {neuralReady ? 'ready' : neuralStatus.status.replace('_', ' ')}</p>
        <p className="mt-3 text-sm leading-6 text-slate-600">Neural training needs {neuralStatus.minimum_profiles} profiles with at least {neuralStatus.minimum_samples_per_profile} samples each. {neuralStatus.eligible_profile_count} currently qualify. Train it in Model laboratory.</p>
      </>}
      {message && <p role="status" className="mt-5 text-sm text-slate-700">{message}</p>}
    </section>

    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8" aria-labelledby="verification-heading">
      <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600">Fixed challenge · {modelType === 'baseline' ? 'baseline' : 'Siamese'} verification</p>
      <h2 id="verification-heading" className="mt-2 text-xl font-semibold">Verify typing rhythm</h2>
      <p className="mt-3 text-sm leading-6 text-slate-600">This local research check processes a fresh timing sample without storing its timing sequence. It saves the decision, score, model, and time under the selected profile. The score is not a probability or a secure login decision.</p>
      <label className="mt-5 flex items-start gap-3 text-sm font-medium">
        <input type="checkbox" checked={consent} disabled={!selected || busy} onChange={(event) => { setConsent(event.target.checked); setResult(null) }} className="mt-1" />
        I consent to processing my typing timing and saving the decision summary for this verification.
      </label>
      <ChallengeCapture key={`${selectedId ?? 'none'}-${modelType}-${consent}`} enabled={!!selected && ready && consent && !busy}
        actionLabel="Verify sample" onSequence={verify} />
      {result && <section aria-label="Verification result" className={`mt-7 rounded-xl border p-5 ${result.accepted ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'}`}>
        <h3 className="text-lg font-semibold">{result.accepted ? 'Accepted' : 'Rejected'} by {result.model_type === 'siamese' ? 'Siamese model' : 'baseline'}</h3>
        <p className="mt-2 text-sm">Similarity {result.similarity_score.toFixed(3)} · threshold {result.decision_threshold.toFixed(3)} (higher is closer)</p>
        <p className="mt-2 text-sm leading-6">{result.explanation}</p>
        <p className="mt-3 text-xs leading-5 text-slate-600">{result.model_version}. Calibration used {result.calibration.genuine_count} genuine and {result.calibration.impostor_count} impostor validation samples. {result.calibration.session_disjoint ? 'Validation recordings came from separate sessions.' : 'Training and validation may share a collection session.'}</p>
      </section>}
    </section>
  </div>
    <section aria-labelledby="trial-history" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <h2 id="trial-history" className="text-xl font-semibold">Recent verification trials</h2>
      <p className="mt-2 text-sm text-slate-600">Only decisions, scores, model versions, and timestamps are saved. Fresh timing sequences are not stored.</p>
      {!loading && trials.length === 0 && <p className="mt-4 text-sm text-slate-600">No verification trials yet.</p>}
      {trials.length > 0 && <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[44rem] text-left text-sm">
        <thead><tr className="border-b border-slate-200"><th className="py-2">Time</th><th>Profile</th><th>Model version</th><th>Decision</th><th>Similarity</th><th>Threshold</th></tr></thead>
        <tbody>{trials.map((trial) => <tr key={trial.id} className="border-b border-slate-100"><td className="py-2">{new Date(trial.created_at).toLocaleString()}</td><td>{profiles.find((profile) => profile.id === trial.profile_id)?.display_name ?? `Profile ${trial.profile_id}`}</td><td>{trial.model_version}</td><td>{trial.accepted ? 'Accepted' : 'Rejected'}</td><td>{trial.similarity_score.toFixed(3)}</td><td>{trial.decision_threshold.toFixed(3)}</td></tr>)}</tbody>
      </table></div>}
    </section>
  </div>
}
