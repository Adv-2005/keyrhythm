import { useEffect, useState } from 'react'
import { getHealth } from './api'

const sections = [
  { id: 'overview', label: 'Overview', milestone: 1 },
  { id: 'enrolment', label: 'Enrolment', milestone: 2 },
  { id: 'authentication', label: 'Authentication', milestone: 3 },
  { id: 'laboratory', label: 'Model laboratory', milestone: 4 },
  { id: 'evaluation', label: 'Evaluation', milestone: 5 },
] as const

type SectionId = (typeof sections)[number]['id']
type ConnectionStatus = 'checking' | 'connected' | 'unavailable'

const connectionLabels: Record<ConnectionStatus, string> = {
  checking: 'Checking API…',
  connected: 'API connected',
  unavailable: 'API unavailable',
}

function App() {
  const [section, setSection] = useState<SectionId>('overview')
  const [connection, setConnection] = useState<ConnectionStatus>('checking')

  useEffect(() => {
    const controller = new AbortController()
    getHealth(controller.signal)
      .then(() => setConnection('connected'))
      .catch(() => {
        if (!controller.signal.aborted) setConnection('unavailable')
      })
    return () => controller.abort()
  }, [])

  const activeSection = sections.find((item) => item.id === section)!

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 lg:flex">
      <aside className="border-b border-slate-200 bg-white lg:flex lg:w-64 lg:flex-col lg:border-b-0 lg:border-r">
        <div className="px-6 py-7">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-lg font-bold text-white" aria-hidden="true">K</div>
            <div>
              <div className="text-lg font-semibold leading-tight tracking-tight">KeyRhythm</div>
              <div className="text-xs text-slate-500">Research workspace</div>
            </div>
          </div>
        </div>
        <nav aria-label="Primary" className="flex gap-1 overflow-x-auto px-3 pb-4 lg:flex-col lg:pb-0">
          {sections.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-current={section === item.id ? 'page' : undefined}
              onClick={() => setSection(item.id)}
              className={`shrink-0 rounded-lg px-4 py-2.5 text-left text-sm font-medium transition-colors lg:w-full ${section === item.id ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="hidden px-6 pb-7 pt-8 text-xs leading-5 text-slate-500 lg:mt-auto lg:block">
          Academic research prototype<br />Milestone 1 foundation
        </div>
      </aside>

      <main className="mx-auto w-full max-w-6xl px-5 py-8 sm:px-8 lg:px-12 lg:py-12">
        <header className="mb-9 flex flex-wrap items-start justify-between gap-5">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-indigo-600">Keystroke dynamics research</p>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{activeSection.label}</h1>
          </div>
          <div
            role="status"
            aria-live="polite"
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-medium ${connection === 'connected' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : connection === 'unavailable' ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-slate-200 bg-white text-slate-600'}`}
          >
            <span className={`h-2 w-2 rounded-full ${connection === 'connected' ? 'bg-emerald-500' : connection === 'unavailable' ? 'bg-rose-500' : 'bg-slate-400'}`} aria-hidden="true" />
            {connectionLabels[connection]}
          </div>
        </header>

        {section === 'overview' ? <Overview onNavigate={setSection} /> : (
          <section className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm sm:p-12" aria-labelledby="upcoming-title">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">Milestone {activeSection.milestone}</p>
            <h2 id="upcoming-title" className="text-2xl font-semibold tracking-tight">{activeSection.label} is planned</h2>
            <p className="mt-3 max-w-2xl leading-7 text-slate-600">This workspace will show real collected data and model results as each milestone is completed.</p>
            <button type="button" className="mt-7 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50" onClick={() => setSection('overview')}>Back to overview</button>
          </section>
        )}
      </main>
    </div>
  )
}

function Overview({ onNavigate }: { onNavigate: (section: SectionId) => void }) {
  return (
    <div className="space-y-7">
      <section className="overflow-hidden rounded-2xl bg-indigo-950 p-8 text-white shadow-sm sm:p-10">
        <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-indigo-200">Continuous authentication study</p>
        <h2 className="max-w-2xl text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">Explore whether typing rhythm can help verify a user over time.</h2>
        <p className="mt-4 max-w-2xl leading-7 text-indigo-100">KeyRhythm will compare a conventional verifier with a Siamese neural network using consented, timing-only samples from a fixed typing challenge.</p>
        <button type="button" onClick={() => onNavigate('enrolment')} className="mt-7 rounded-lg bg-white px-5 py-3 text-sm font-semibold text-indigo-950 hover:bg-indigo-50">View enrolment plan</button>
      </section>

      <section aria-labelledby="workflow-heading">
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">Project workflow</p>
            <h2 id="workflow-heading" className="text-xl font-semibold tracking-tight">From samples to evidence</h2>
          </div>
          <span className="text-sm text-slate-500">Foundation in progress</span>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {[
            { number: '01', title: 'Collect', text: 'Enrol consenting participants through a fixed challenge and capture timing features.', milestone: 'Milestone 2' },
            { number: '02', title: 'Compare', text: 'Fit a simple baseline, then train a Siamese model on carefully split samples.', milestone: 'Milestones 3–4' },
            { number: '03', title: 'Evaluate', text: 'Measure verification results on held-out recordings and inspect limitations.', milestone: 'Milestone 5' },
          ].map((item) => (
            <article key={item.number} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <span className="text-sm font-semibold text-indigo-600">{item.number}</span>
              <h3 className="mt-4 text-lg font-semibold">{item.title}</h3>
              <p className="mt-2 min-h-20 text-sm leading-6 text-slate-600">{item.text}</p>
              <p className="mt-5 border-t border-slate-100 pt-4 text-xs font-medium uppercase tracking-wider text-slate-500">{item.milestone}</p>
            </article>
          ))}
        </div>
      </section>

      <p className="text-sm leading-6 text-slate-500">This is a local academic prototype. It is not intended to replace passwords or multifactor authentication.</p>
    </div>
  )
}

export default App
