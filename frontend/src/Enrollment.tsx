import { useEffect, useState } from 'react'
import { createProfile, deleteProfile, listProfiles, submitSample, type Profile } from './api'
import ChallengeCapture from './ChallengeCapture'
import type { TimingSequence } from './timing'

export default function Enrollment() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [label, setLabel] = useState('')
  const [consent, setConsent] = useState(false)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [sessionId] = useState(() => crypto.randomUUID())
  const selected = profiles.find((profile) => profile.id === selectedId)

  useEffect(() => {
    const controller = new AbortController()
    listProfiles(controller.signal).then((items) => {
      setProfiles(items)
      setSelectedId(items[0]?.id ?? null)
    }).catch(() => { if (!controller.signal.aborted) setError('Could not load profiles. Check the API connection.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [])

  async function addProfile(event: React.FormEvent) {
    event.preventDefault()
    if (!label.trim()) return
    setBusy(true)
    setError('')
    try {
      const profile = await createProfile(label.trim())
      setProfiles((items) => [...items, profile])
      setSelectedId(profile.id)
      setConsent(false)
      setLabel('')
      setMessage('Profile created. Read and accept the consent notice to start.')
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Could not create profile.')
    } finally { setBusy(false) }
  }

  async function removeProfile() {
    if (!selected || !window.confirm(`Delete ${selected.display_name} and all ${selected.sample_count} timing samples?`)) return
    setBusy(true)
    setError('')
    try {
      await deleteProfile(selected.id)
      const remaining = profiles.filter((profile) => profile.id !== selected.id)
      setProfiles(remaining)
      setSelectedId(remaining[0]?.id ?? null)
      setConsent(false)
      setMessage('Profile and its samples deleted.')
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Could not delete profile.')
    } finally { setBusy(false) }
  }

  async function saveSample(sequence: TimingSequence): Promise<string> {
    if (!selected || !consent) throw new Error('Select a profile and consent before saving.')
    setBusy(true)
    try {
      const result = await submitSample(selected.id, sessionId, sequence)
      setProfiles((items) => items.map((profile) => profile.id === selected.id
        ? { ...profile, sample_count: result.sample_count,
            enrollment_status: result.sample_count >= profile.enrollment_target ? 'ready' : 'collecting' }
        : profile))
      return `Sample saved. ${result.sample_count} of ${selected.enrollment_target} collected.`
    } finally { setBusy(false) }
  }

  return <div className="grid gap-6 xl:grid-cols-[18rem_1fr]">
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" aria-labelledby="profile-heading">
      <h2 id="profile-heading" className="text-lg font-semibold">Profiles</h2>
      <p className="mt-2 text-sm text-slate-600">Use a pseudonymous label. Timing data remains on this local machine.</p>
      {loading && <p role="status" className="mt-3 text-sm text-slate-600">Loading profiles…</p>}
      {error && <p role="alert" className="mt-3 text-sm text-rose-700">{error}</p>}
      <form onSubmit={addProfile} className="mt-5 space-y-3">
        <label htmlFor="profile-label" className="block text-sm font-medium">New profile label</label>
        <input id="profile-label" value={label} maxLength={80} onChange={(event) => setLabel(event.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2" placeholder="Participant 01" />
        <button disabled={busy || loading || !label.trim()} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Create profile</button>
      </form>
      <label htmlFor="profile-select" className="mt-7 block text-sm font-medium">Selected profile</label>
      <select id="profile-select" value={selectedId ?? ''} disabled={busy || loading || profiles.length === 0}
        onChange={(event) => { setSelectedId(Number(event.target.value)); setConsent(false); setMessage('') }}
        className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2">
        {profiles.length === 0 && <option value="">No profiles yet</option>}
        {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.display_name}</option>)}
      </select>
      {!loading && !selected && !error && <p className="mt-4 text-sm text-slate-600">No profiles yet. Create one to begin enrolment.</p>}
      {selected && <>
        <p className="mt-4 text-sm text-slate-600">{selected.sample_count} / {selected.enrollment_target} samples · {selected.enrollment_status}</p>
        <progress aria-label="Enrolment progress" className="mt-2 w-full accent-indigo-600" value={Math.min(selected.sample_count, selected.enrollment_target)} max={selected.enrollment_target} />
        <button type="button" onClick={removeProfile} disabled={busy} className="mt-5 text-sm font-medium text-rose-700 hover:underline">Delete profile and samples</button>
      </>}
      {message && <p role="status" className="mt-5 text-sm text-slate-700">{message}</p>}
    </section>

    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8" aria-labelledby="challenge-heading">
      <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600">Fixed challenge · version 1</p>
      <h2 id="challenge-heading" className="mt-2 text-xl font-semibold">Typing enrolment</h2>
      <p className="mt-3 text-sm leading-6 text-slate-600">Typing rhythm is behavioural biometric data. By checking the box, you consent to collecting and storing timing sequences for this local research experiment. No typed text or key values are sent or saved. You can delete your profile and its samples at any time.</p>
      <label className="mt-5 flex items-start gap-3 text-sm font-medium">
        <input type="checkbox" checked={consent} disabled={!selected || busy} onChange={(event) => setConsent(event.target.checked)} className="mt-1" />
        I consent to local collection of my typing timing data.
      </label>
      <ChallengeCapture key={`${selectedId ?? 'none'}-${consent}`} enabled={!!selected && consent && !busy}
        actionLabel="Save sample" onSequence={saveSample} />
    </section>
  </div>
}
