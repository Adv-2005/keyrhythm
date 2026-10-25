import { useEffect, useState } from 'react'
import { authenticate, getModelStatus, listProfiles, trainBaseline,
  type AuthenticationResult, type ModelStatus, type Profile } from './api'
import ChallengeCapture from './ChallengeCapture'
import type { TimingSequence } from './timing'

export default function Authentication() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [status, setStatus] = useState<ModelStatus | null>(null)
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [result, setResult] = useState<AuthenticationResult | null>(null)
  const [sessionId] = useState(() => crypto.randomUUID())
  const selected = profiles.find((profile) => profile.id === selectedId)
  const model = status?.profiles.find((item) => item.profile_id === selectedId)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([listProfiles(controller.signal), getModelStatus(controller.signal)])
      .then(([items, modelStatus]) => {
        setProfiles(items)
        setSelectedId(items[0]?.id ?? null)
        setStatus(modelStatus)
      })
      .catch(() => { if (!controller.signal.aborted) setMessage('Could not load profiles or model status. Check the API connection.') })
    return () => controller.abort()
  }, [])

  async function train() {
    setBusy(true)
    setResult(null)
    try {
      await trainBaseline()
      setStatus(await getModelStatus())
      setMessage('Baseline fitted and calibrated on the current enrollment samples.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not train the baseline.')
    } finally { setBusy(false) }
  }

  async function verify(sequence: TimingSequence): Promise<string> {
    if (!selected || !consent) throw new Error('Select a profile and consent before verification.')
    setBusy(true)
    setResult(null)
    try {
      const verification = await authenticate(selected.id, sessionId, sequence)
      setResult(verification)
      return 'Verification complete. This result is experimental.'
    } catch (error) {
      if (error instanceof Error && error.message.includes('retrain')) {
        setStatus(await getModelStatus())
      }
      throw error
    } finally { setBusy(false) }
  }

  return <div className="grid gap-6 xl:grid-cols-[18rem_1fr]">
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" aria-labelledby="verification-profile-heading">
      <h2 id="verification-profile-heading" className="text-lg font-semibold">Baseline model</h2>
      <label htmlFor="verification-profile" className="mt-5 block text-sm font-medium">Selected profile</label>
      <select id="verification-profile" value={selectedId ?? ''} disabled={busy || profiles.length === 0}
        onChange={(event) => { setSelectedId(Number(event.target.value)); setConsent(false); setResult(null); setMessage('') }}
        className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2">
        {profiles.length === 0 && <option value="">No profiles yet</option>}
        {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.display_name}</option>)}
      </select>
      {selected && <p className="mt-4 text-sm text-slate-600">{selected.sample_count} enrollment samples</p>}
      {status && <>
        <p className="mt-3 text-sm text-slate-600">Model: {model?.status.replace('_', ' ') ?? 'unavailable'}</p>
        <p className="mt-3 text-sm leading-6 text-slate-600">Training needs {status.minimum_profiles} profiles with at least {status.minimum_samples_per_profile} samples each. {status.eligible_profile_count} currently qualify.</p>
        <button type="button" onClick={train} disabled={busy || status.eligible_profile_count < status.minimum_profiles}
          className="mt-5 rounded-lg border border-indigo-300 px-4 py-2 text-sm font-semibold text-indigo-700 disabled:opacity-50">Train baseline</button>
      </>}
      {message && <p role="status" className="mt-5 text-sm text-slate-700">{message}</p>}
    </section>

    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8" aria-labelledby="verification-heading">
      <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600">Fixed challenge · baseline verification</p>
      <h2 id="verification-heading" className="mt-2 text-xl font-semibold">Verify typing rhythm</h2>
      <p className="mt-3 text-sm leading-6 text-slate-600">This local research check processes a fresh timing sample without storing it. The score measures similarity to the selected profile; it is not a probability or a secure login decision.</p>
      <label className="mt-5 flex items-start gap-3 text-sm font-medium">
        <input type="checkbox" checked={consent} disabled={!selected || busy} onChange={(event) => { setConsent(event.target.checked); setResult(null) }} className="mt-1" />
        I consent to processing my typing timing for this verification.
      </label>
      <ChallengeCapture key={`${selectedId ?? 'none'}-${consent}`} enabled={!!selected && model?.status === 'ready' && consent && !busy}
        actionLabel="Verify sample" onSequence={verify} />
      {result && <section aria-label="Verification result" className={`mt-7 rounded-xl border p-5 ${result.accepted ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'}`}>
        <h3 className="text-lg font-semibold">{result.accepted ? 'Accepted by baseline' : 'Rejected by baseline'}</h3>
        <p className="mt-2 text-sm">Similarity {result.similarity_score.toFixed(3)} · threshold {result.decision_threshold.toFixed(3)} (higher is closer)</p>
        <p className="mt-2 text-sm leading-6">{result.explanation}</p>
        <p className="mt-3 text-xs leading-5 text-slate-600">{result.model_version}. Calibration used {result.calibration.genuine_count} genuine and {result.calibration.impostor_count} impostor validation samples. {result.calibration.session_disjoint ? 'Validation recordings came from separate sessions.' : 'Training and validation may share a collection session.'}</p>
      </section>}
    </section>
  </div>
}
