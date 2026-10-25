import { useEffect, useRef, useState } from 'react'
import { createProfile, deleteProfile, listProfiles, submitSample, type Profile } from './api'
import { CHALLENGE, TimingCapture } from './timing'

export default function Enrollment() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [label, setLabel] = useState('')
  const [typed, setTyped] = useState('')
  const [consent, setConsent] = useState(false)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [, setCaptureRevision] = useState(0)
  const capture = useRef(new TimingCapture())
  const [sessionId] = useState(() => crypto.randomUUID())
  const selected = profiles.find((profile) => profile.id === selectedId)

  useEffect(() => {
    const controller = new AbortController()
    listProfiles(controller.signal).then((items) => {
      setProfiles(items)
      setSelectedId(items[0]?.id ?? null)
    }).catch(() => { if (!controller.signal.aborted) setMessage('Could not load profiles. Check the API connection.') })
    return () => controller.abort()
  }, [])

  function restart() {
    capture.current = new TimingCapture()
    setTyped('')
    setMessage('Sample restarted. Type the challenge from the beginning.')
  }

  async function addProfile(event: React.FormEvent) {
    event.preventDefault()
    if (!label.trim()) return
    setBusy(true)
    try {
      const profile = await createProfile(label.trim())
      setProfiles((items) => [...items, profile])
      setSelectedId(profile.id)
      setConsent(false)
      setLabel('')
      restart()
      setMessage('Profile created. Read and accept the consent notice to start.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not create profile.')
    } finally { setBusy(false) }
  }

  async function removeProfile() {
    if (!selected || !window.confirm(`Delete ${selected.display_name} and all ${selected.sample_count} timing samples?`)) return
    setBusy(true)
    try {
      await deleteProfile(selected.id)
      const remaining = profiles.filter((profile) => profile.id !== selected.id)
      setProfiles(remaining)
      setSelectedId(remaining[0]?.id ?? null)
      setConsent(false)
      restart()
      setMessage('Profile and its samples deleted.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not delete profile.')
    } finally { setBusy(false) }
  }

  async function saveSample() {
    if (!selected || !consent || busy) return
    const sequence = capture.current.complete(typed)
    if (!sequence) {
      setMessage('Finish the exact challenge and release every key, or restart this sample.')
      return
    }
    setBusy(true)
    try {
      const result = await submitSample(selected.id, sessionId, sequence)
      setProfiles((items) => items.map((profile) => profile.id === selected.id
        ? { ...profile, sample_count: result.sample_count,
            enrollment_status: result.sample_count >= profile.enrollment_target ? 'ready' : 'collecting' }
        : profile))
      restart()
      setMessage(`Sample saved. ${result.sample_count} of ${selected.enrollment_target} collected.`)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not save sample. You can retry.')
    } finally { setBusy(false) }
  }

  const inputEnabled = !!selected && consent && !busy
  const ready = inputEnabled && !capture.current.error && capture.current.complete(typed) !== null

  return <div className="grid gap-6 xl:grid-cols-[18rem_1fr]">
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" aria-labelledby="profile-heading">
      <h2 id="profile-heading" className="text-lg font-semibold">Profiles</h2>
      <p className="mt-2 text-sm text-slate-600">Use a pseudonymous label. Timing data remains on this local machine.</p>
      <form onSubmit={addProfile} className="mt-5 space-y-3">
        <label htmlFor="profile-label" className="block text-sm font-medium">New profile label</label>
        <input id="profile-label" value={label} maxLength={80} onChange={(event) => setLabel(event.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2" placeholder="Participant 01" />
        <button disabled={busy || !label.trim()} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Create profile</button>
      </form>
      <label htmlFor="profile-select" className="mt-7 block text-sm font-medium">Selected profile</label>
      <select id="profile-select" value={selectedId ?? ''} disabled={busy || profiles.length === 0}
        onChange={(event) => { setSelectedId(Number(event.target.value)); setConsent(false); restart() }}
        className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2">
        {profiles.length === 0 && <option value="">No profiles yet</option>}
        {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.display_name}</option>)}
      </select>
      {selected && <>
        <p className="mt-4 text-sm text-slate-600">{selected.sample_count} / {selected.enrollment_target} samples · {selected.enrollment_status}</p>
        <button type="button" onClick={removeProfile} disabled={busy} className="mt-5 text-sm font-medium text-rose-700 hover:underline">Delete profile and samples</button>
      </>}
    </section>

    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8" aria-labelledby="challenge-heading">
      <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600">Fixed challenge · version 1</p>
      <h2 id="challenge-heading" className="mt-2 text-xl font-semibold">Typing enrolment</h2>
      <p className="mt-3 text-sm leading-6 text-slate-600">Typing rhythm is behavioural biometric data. By checking the box, you consent to collecting and storing timing sequences for this local research experiment. No typed text or key values are sent or saved. You can delete your profile and its samples at any time.</p>
      <label className="mt-5 flex items-start gap-3 text-sm font-medium">
        <input type="checkbox" checked={consent} disabled={!selected || busy} onChange={(event) => {
          setConsent(event.target.checked); restart()
        }} className="mt-1" />
        I consent to local collection of my typing timing data.
      </label>
      <div className="mt-7 rounded-xl border border-indigo-100 bg-indigo-50 p-5 text-lg font-medium leading-8" aria-label="Typing challenge">{CHALLENGE}</div>
      <label htmlFor="challenge-input" className="mt-6 block text-sm font-medium">Type the sentence exactly</label>
      <input id="challenge-input" type="text" value={typed} disabled={!inputEnabled || !!capture.current.error}
        autoComplete="off" autoCorrect="off" autoCapitalize="off" spellCheck={false}
        onKeyDown={(event) => {
          capture.current.keyDown(event.key, event.code, event.timeStamp, event.repeat, event.ctrlKey || event.altKey || event.metaKey)
          if (capture.current.error) { event.preventDefault(); setMessage(capture.current.error) }
        }}
        onKeyUp={(event) => { capture.current.keyUp(event.key, event.code, event.timeStamp); setCaptureRevision((n) => n + 1); if (capture.current.error) setMessage(capture.current.error) }}
        onChange={(event) => { capture.current.checkInput(event.target.value); setTyped(event.target.value); if (capture.current.error) setMessage(capture.current.error) }}
        onBeforeInput={(event) => { const kind = (event.nativeEvent as InputEvent).inputType; if (kind && kind !== 'insertText') { capture.current.invalidate('Edits and pasted text are not accepted. Restart this sample.'); setMessage(capture.current.error ?? '') } }}
        onPaste={(event) => { event.preventDefault(); capture.current.invalidate('Pasted text is not accepted. Restart this sample.'); setMessage(capture.current.error ?? '') }}
        onDrop={(event) => { event.preventDefault(); capture.current.invalidate('Dropped text is not accepted. Restart this sample.'); setMessage(capture.current.error ?? '') }}
        onCut={(event) => { event.preventDefault(); capture.current.invalidate('Edits are not accepted. Restart this sample.'); setMessage(capture.current.error ?? '') }}
        onCompositionStart={() => { capture.current.invalidate('Composition input is not supported. Restart this sample.'); setMessage(capture.current.error ?? '') }}
        onBlur={() => { if (typed && !capture.current.complete(typed)) { capture.current.invalidate('Focus was lost. Restart this sample.'); setMessage(capture.current.error ?? '') } }}
        className="mt-2 w-full rounded-lg border border-slate-300 px-4 py-3 disabled:bg-slate-100" />
      <p className="mt-2 text-sm text-slate-500">{typed.length} / {CHALLENGE.length} characters. Corrections require a restart.</p>
      <div className="mt-6 flex flex-wrap gap-3">
        <button type="button" onClick={saveSample} disabled={!ready || busy} className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">Save sample</button>
        <button type="button" onClick={restart} disabled={!inputEnabled} className="rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-semibold disabled:opacity-50">Restart sample</button>
      </div>
      {message && <p role="status" className="mt-5 text-sm text-slate-700">{message}</p>}
    </section>
  </div>
}
