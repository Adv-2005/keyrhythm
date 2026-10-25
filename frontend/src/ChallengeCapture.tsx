import { useRef, useState } from 'react'
import { CHALLENGE, TimingCapture, type TimingSequence } from './timing'

type Props = {
  enabled: boolean
  actionLabel: string
  onSequence: (sequence: TimingSequence) => Promise<string>
}

export default function ChallengeCapture({ enabled, actionLabel, onSequence }: Props) {
  const [typed, setTyped] = useState('')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const [, setRevision] = useState(0)
  const capture = useRef(new TimingCapture())
  const ready = enabled && !saving && !capture.current.error && capture.current.complete(typed) !== null

  function restart() {
    capture.current = new TimingCapture()
    setTyped('')
    setMessage('Sample restarted. Type the challenge from the beginning.')
  }

  function invalidate(message: string) {
    capture.current.invalidate(message)
    setMessage(message)
  }

  async function submit() {
    if (!ready) return
    const sequence = capture.current.complete(typed)
    if (!sequence) return
    setSaving(true)
    try {
      const resultMessage = await onSequence(sequence)
      restart()
      setMessage(resultMessage)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not process the sample. You can retry.')
    } finally { setSaving(false) }
  }

  return <>
    <div className="mt-7 rounded-xl border border-indigo-100 bg-indigo-50 p-5 text-lg font-medium leading-8" aria-label="Typing challenge">{CHALLENGE}</div>
    <label htmlFor="challenge-input" className="mt-6 block text-sm font-medium">Type the sentence exactly</label>
    <input id="challenge-input" type="text" value={typed} disabled={!enabled || saving || !!capture.current.error}
      autoComplete="off" autoCorrect="off" autoCapitalize="off" spellCheck={false}
      onKeyDown={(event) => {
        capture.current.keyDown(event.key, event.code, event.timeStamp, event.repeat, event.ctrlKey || event.altKey || event.metaKey)
        if (capture.current.error) { event.preventDefault(); setMessage(capture.current.error) }
      }}
      onKeyUp={(event) => { capture.current.keyUp(event.key, event.code, event.timeStamp); setRevision((n) => n + 1); if (capture.current.error) setMessage(capture.current.error) }}
      onChange={(event) => { capture.current.checkInput(event.target.value); setTyped(event.target.value); if (capture.current.error) setMessage(capture.current.error) }}
      onBeforeInput={(event) => { const kind = (event.nativeEvent as InputEvent).inputType; if (kind && kind !== 'insertText') { event.preventDefault(); invalidate('Edits and pasted text are not accepted. Restart this sample.') } }}
      onPaste={(event) => { event.preventDefault(); invalidate('Pasted text is not accepted. Restart this sample.') }}
      onDrop={(event) => { event.preventDefault(); invalidate('Dropped text is not accepted. Restart this sample.') }}
      onCut={(event) => { event.preventDefault(); invalidate('Edits are not accepted. Restart this sample.') }}
      onCompositionStart={() => invalidate('Composition input is not supported. Restart this sample.')}
      onBlur={() => { if (typed && !capture.current.complete(typed)) invalidate('Focus was lost. Restart this sample.') }}
      className="mt-2 w-full rounded-lg border border-slate-300 px-4 py-3 disabled:bg-slate-100" />
    <p className="mt-2 text-sm text-slate-500">{typed.length} / {CHALLENGE.length} characters. Corrections require a restart.</p>
    <div className="mt-6 flex flex-wrap gap-3">
      <button type="button" onClick={submit} disabled={!ready} className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{actionLabel}</button>
      <button type="button" onClick={restart} disabled={!enabled || saving} className="rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-semibold disabled:opacity-50">Restart sample</button>
    </div>
    {message && <p role="status" className="mt-5 text-sm text-slate-700">{message}</p>}
  </>
}
