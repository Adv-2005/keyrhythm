import { useEffect, useState } from 'react'
import { getHealth } from './api'
import Authentication from './Authentication'
import Enrollment from './Enrollment'
import Evaluation from './Evaluation'
import ModelLaboratory from './ModelLaboratory'
import Overview from './Overview'

const sections = [
  { id: 'overview', label: 'Overview' },
  { id: 'enrolment', label: 'Enrolment' },
  { id: 'authentication', label: 'Authentication' },
  { id: 'laboratory', label: 'Model laboratory' },
  { id: 'evaluation', label: 'Evaluation' },
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
    setConnection('checking')
    getHealth(controller.signal)
      .then(() => setConnection('connected'))
      .catch(() => {
        if (!controller.signal.aborted) setConnection('unavailable')
      })
    return () => controller.abort()
  }, [section])

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
          Academic research prototype<br />Milestone 6 dashboard
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

        {section === 'overview' ? <Overview onNavigate={setSection} /> : section === 'enrolment' ? <Enrollment /> : section === 'authentication' ? <Authentication /> : section === 'laboratory' ? <ModelLaboratory onNavigate={setSection} /> : <Evaluation />}
      </main>
    </div>
  )
}

export default App
