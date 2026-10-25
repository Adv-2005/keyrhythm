import { useEffect, useState } from 'react'
import { getModelStatus, getSiameseStatus, listExperiments, listProfiles,
  type ExperimentSummary, type ModelStatus, type Profile, type SiameseStatus } from './api'

type Snapshot = {
  profiles: Profile[]
  baseline: ModelStatus
  siamese: SiameseStatus
  latest: ExperimentSummary | null
}

export default function Overview({ onNavigate }: { onNavigate: (section: 'enrolment' | 'authentication' | 'laboratory' | 'evaluation') => void }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load(signal?: AbortSignal) {
    setLoading(true)
    setError('')
    try {
      const [profiles, baseline, siamese, experiments] = await Promise.all([
        listProfiles(signal), getModelStatus(signal), getSiameseStatus(signal), listExperiments(signal),
      ])
      if (!signal?.aborted) setSnapshot({ profiles, baseline, siamese, latest: experiments[0] ?? null })
    } catch {
      if (!signal?.aborted) setError('Could not load the dashboard. Check the API connection and retry.')
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [])

  const sampleCount = snapshot?.profiles.reduce((total, profile) => total + profile.sample_count, 0) ?? 0
  const baselineReady = snapshot?.baseline.profiles.filter((profile) => profile.status === 'ready').length ?? 0

  return <div className="space-y-7">
    <section className="overflow-hidden rounded-2xl bg-indigo-950 p-8 text-white shadow-sm sm:p-10">
      <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-indigo-200">Continuous authentication study</p>
      <h2 className="max-w-2xl text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">Explore whether typing rhythm can help verify a user over time.</h2>
      <p className="mt-4 max-w-2xl leading-7 text-indigo-100">Collect consented timing samples, train both models, then compare them on held-out recordings.</p>
      <div className="mt-7 flex flex-wrap gap-3">
        <button type="button" onClick={() => onNavigate('enrolment')} className="rounded-lg bg-white px-5 py-3 text-sm font-semibold text-indigo-950 hover:bg-indigo-50">Start enrolment</button>
        <button type="button" onClick={() => onNavigate('authentication')} className="rounded-lg border border-indigo-300 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-900">Verify a sample</button>
      </div>
    </section>

    <section aria-labelledby="overview-state" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="overview-state" className="text-xl font-semibold">Current workspace</h2>
        <button type="button" onClick={() => void load()} disabled={loading} className="text-sm font-medium text-indigo-700 disabled:opacity-50">Refresh</button>
      </div>
      {loading && !snapshot && <p role="status" className="mt-4 text-sm text-slate-600">Loading workspace data…</p>}
      {error && <p role="alert" className="mt-4 text-sm text-rose-700">{error}</p>}
      {snapshot && <>
        {loading && <p role="status" className="mt-3 text-sm text-slate-600">Refreshing workspace data…</p>}
        <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Stat label="Profiles" value={String(snapshot.profiles.length)} />
          <Stat label="Timing samples" value={String(sampleCount)} />
          <Stat label="Baseline profiles ready" value={`${baselineReady} / ${snapshot.profiles.length}`} />
          <Stat label="Siamese model" value={snapshot.siamese.status.replace('_', ' ')} />
        </div>
        <p className="mt-5 text-sm text-slate-600">Authentication opens with the distance baseline selected; you can choose the Siamese model there. Baseline {snapshot.baseline.model_version}; neural {snapshot.siamese.model_version}. Adding samples can make trained models stale.</p>
        {snapshot.profiles.length === 0 && <p className="mt-3 text-sm text-slate-600">No profiles yet. Create a pseudonymous profile to begin collecting samples.</p>}
      </>}
    </section>

    <section aria-labelledby="latest-evaluation" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="latest-evaluation" className="text-xl font-semibold">Latest saved evaluation</h2>
        <button type="button" onClick={() => onNavigate('evaluation')} className="text-sm font-medium text-indigo-700">Open evaluation</button>
      </div>
      {snapshot?.latest ? <>
        <p className="mt-3 text-sm text-slate-600">Run #{snapshot.latest.id} · {new Date(snapshot.latest.created_at).toLocaleString()} · {snapshot.latest.test_recording_count} held-out recordings</p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <EvaluationCard label="Distance baseline" metrics={snapshot.latest.baseline} />
          <EvaluationCard label="Siamese CNN" metrics={snapshot.latest.siamese} />
        </div>
        <p className="mt-3 text-xs text-slate-500">These results belong to the saved dataset snapshot. Open the experiment for denominators and limitations.</p>
      </> : !loading && !error && <p className="mt-4 text-sm text-slate-600">No evaluation has been saved. Train the Siamese model, then run a held-out comparison.</p>}
    </section>

    <p className="text-sm leading-6 text-slate-500">This local academic prototype does not replace passwords or multifactor authentication.</p>
  </div>
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p><p className="mt-2 text-2xl font-semibold capitalize text-slate-900">{value}</p></div>
}

function EvaluationCard({ label, metrics }: { label: string; metrics: ExperimentSummary['baseline'] }) {
  return <div className="rounded-xl border border-slate-200 p-4"><h3 className="font-semibold">{label}</h3><p className="mt-2 text-sm text-slate-600">FAR {(metrics.false_acceptance_rate * 100).toFixed(1)}% · FRR {(metrics.false_rejection_rate * 100).toFixed(1)}%</p><p className="mt-1 text-xs text-slate-500">AUC {metrics.roc_auc === null ? 'insufficient attempts' : metrics.roc_auc.toFixed(3)}</p></div>
}
