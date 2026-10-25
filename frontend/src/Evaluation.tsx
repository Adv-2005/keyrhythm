import { useEffect, useState } from 'react'
import { experimentPlotUrl, getExperiment, listExperiments, runEvaluation,
  type EvaluationMetrics, type Experiment, type ExperimentSummary } from './api'

const percent = (value: number) => `${(value * 100).toFixed(1)}%`
const optionalPercent = (value: number | null) => value === null ? 'Insufficient attempts' : percent(value)
const optionalAuc = (value: number | null) => value === null ? 'Insufficient attempts' : value.toFixed(3)

function MetricRow({ label, baseline, siamese }: { label: string; baseline: string; siamese: string }) {
  return <tr className="border-b border-slate-100"><th scope="row" className="py-2 pr-4 text-left font-medium">{label}</th><td>{baseline}</td><td>{siamese}</td></tr>
}

function Comparison({ baseline, siamese }: { baseline: EvaluationMetrics; siamese: EvaluationMetrics }) {
  return <div className="overflow-x-auto"><table className="w-full text-left text-sm">
    <caption className="mb-3 text-left text-lg font-semibold">Held-out model comparison</caption>
    <thead><tr className="border-b border-slate-200"><th className="pb-2">Metric</th><th>Baseline</th><th>Siamese</th></tr></thead>
    <tbody>
      <MetricRow label="False acceptance rate" baseline={percent(baseline.false_acceptance_rate)} siamese={percent(siamese.false_acceptance_rate)} />
      <MetricRow label="False rejection rate" baseline={percent(baseline.false_rejection_rate)} siamese={percent(siamese.false_rejection_rate)} />
      <MetricRow label="ROC-AUC" baseline={optionalAuc(baseline.roc_auc)} siamese={optionalAuc(siamese.roc_auc)} />
      <MetricRow label="Equal error rate" baseline={optionalPercent(baseline.equal_error_rate)} siamese={optionalPercent(siamese.equal_error_rate)} />
      <MetricRow label="Precision" baseline={baseline.precision === null ? 'No accepted attempts' : percent(baseline.precision)} siamese={siamese.precision === null ? 'No accepted attempts' : percent(siamese.precision)} />
      <MetricRow label="Recall" baseline={percent(baseline.recall)} siamese={percent(siamese.recall)} />
      <MetricRow label="Genuine attempts" baseline={String(baseline.genuine_count)} siamese={String(siamese.genuine_count)} />
      <MetricRow label="Impostor attempts" baseline={String(baseline.impostor_count)} siamese={String(siamese.impostor_count)} />
    </tbody>
  </table></div>
}

export default function Evaluation() {
  const [history, setHistory] = useState<ExperimentSummary[]>([])
  const [experiment, setExperiment] = useState<Experiment | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    listExperiments(controller.signal).then(async (items) => {
      setHistory(items)
      if (items[0]) setExperiment(await getExperiment(items[0].id, controller.signal))
    }).catch(() => {
      if (!controller.signal.aborted) setMessage('Could not load experiments. Check the API connection.')
    })
    return () => controller.abort()
  }, [])

  async function evaluate() {
    setBusy(true)
    setMessage('Evaluating both models on the saved held-out recordings…')
    try {
      const created = await runEvaluation()
      setExperiment(created)
      setHistory(await listExperiments())
      setMessage('Evaluation saved. Repeating this run returns the existing result for the same model and dataset.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Evaluation failed.')
    } finally { setBusy(false) }
  }

  async function selectExperiment(id: number) {
    setBusy(true)
    try {
      setExperiment(await getExperiment(id))
      setMessage('')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not open experiment.')
    } finally { setBusy(false) }
  }

  const result = experiment?.result
  const baseline = result?.models.baseline.metrics
  const siamese = result?.models.siamese.metrics

  return <div className="space-y-6">
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <h2 className="text-xl font-semibold">Held-out verification experiment</h2>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">Both models use the same recorded test attempts. Training recordings fit references, validation recordings choose thresholds, and test recordings produce the metrics below. Train the Siamese model in Model laboratory before running this comparison.</p>
      <div className="mt-5 flex flex-wrap items-end gap-4">
        <button type="button" onClick={evaluate} disabled={busy}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? 'Evaluating…' : 'Run evaluation'}</button>
        <div><label htmlFor="experiment-select" className="block text-sm font-medium">Saved experiment</label>
          <select id="experiment-select" disabled={busy || history.length === 0} value={experiment?.id ?? ''}
            onChange={(event) => selectExperiment(Number(event.target.value))}
            className="mt-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
            {history.length === 0 && <option value="">None yet</option>}
            {history.map((item) => <option key={item.id} value={item.id}>#{item.id} · {new Date(item.created_at).toLocaleString()}</option>)}
          </select>
        </div>
      </div>
      {message && <p role="status" className="mt-4 text-sm text-slate-700">{message}</p>}
    </section>

    {result && baseline && siamese ? <>
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <Comparison baseline={baseline} siamese={siamese} />
        <p className="mt-4 text-sm text-slate-600">{result.profile_count} profiles · {result.sample_count} recordings · {result.test_recording_count} distinct test recordings · {result.trial_count_per_model} attempts per model. FAR uses {baseline.impostor_count} impostor attempts; FRR uses {baseline.genuine_count} genuine attempts.</p>
      </section>
      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="font-semibold">ROC curve</h3>
          <a href={experimentPlotUrl(experiment!.id, 'roc')} download={`keyrhythm-roc-${experiment!.id}.svg`} className="mt-2 inline-block text-sm text-indigo-700 underline">Download SVG</a>
          <img src={experimentPlotUrl(experiment!.id, 'roc')} alt="ROC curves for baseline and Siamese verifier" className="mt-3 w-full" /></section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="font-semibold">Confusion matrices</h3>
          <a href={experimentPlotUrl(experiment!.id, 'confusion')} download={`keyrhythm-confusion-${experiment!.id}.svg`} className="mt-2 inline-block text-sm text-indigo-700 underline">Download SVG</a>
          <img src={experimentPlotUrl(experiment!.id, 'confusion')} alt="Confusion matrices for baseline and Siamese verifier" className="mt-3 w-full" /></section>
      </div>
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <h3 className="text-lg font-semibold">Profile reference count</h3>
        <p className="mt-2 text-sm text-slate-600">The encoder and scaler stay fixed while each profile reference uses the first N training recordings. Thresholds are recalibrated on validation recordings for each count.</p>
        <div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b border-slate-200"><th className="pb-2">References</th><th>Baseline FAR</th><th>Baseline FRR</th><th>Siamese FAR</th><th>Siamese FRR</th></tr></thead>
          <tbody>{result.reference_count_effect.map((item) => <tr key={item.reference_count} className="border-b border-slate-100"><td className="py-2">{item.reference_count}</td><td>{percent(item.baseline.false_acceptance_rate)}</td><td>{percent(item.baseline.false_rejection_rate)}</td><td>{percent(item.siamese.false_acceptance_rate)}</td><td>{percent(item.siamese.false_rejection_rate)}</td></tr>)}</tbody>
        </table></div>
      </section>
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <h3 className="text-lg font-semibold">Protocol and limits</h3>
        <p className="mt-2 text-sm text-slate-600">{result.protocol_version} · dataset {result.dataset_fingerprint.slice(0, 12)} · {result.model_versions.baseline} versus {result.model_versions.siamese}</p>
        <p className="mt-3 text-sm text-slate-600">{Object.values(result.split_configuration).filter((split) => split.session_disjoint).length} of {result.profile_count} profiles have session-disjoint training, validation, and test partitions.</p>
        <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-600">{result.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
      </section>
    </> : <section className="rounded-2xl border border-slate-200 bg-white p-8 text-sm text-slate-600 shadow-sm">No saved evaluation yet. Collect and train with consenting participants, then run the comparison.</section>}
  </div>
}
