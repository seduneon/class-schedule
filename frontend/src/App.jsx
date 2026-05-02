import { useState } from 'react'
import Phase1 from './pages/Phase1.jsx'
import Phase2 from './pages/Phase2.jsx'

const TABS = [
  { id: 'phase1', label: 'Phase 1 — Assignment' },
  { id: 'phase2', label: 'Phase 2 — Scheduling' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('phase1')
  const [jobId, setJobId] = useState(null)

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center gap-3">
          <div className="h-8 w-8 rounded bg-blue-600 flex items-center justify-center">
            <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-900 leading-none">Class Scheduling</h1>
            <p className="text-xs text-gray-400 mt-0.5">Nazarbayev University — MATH 499</p>
          </div>
        </div>
      </header>

      {/* Tab bar */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <nav className="flex gap-0" aria-label="Tabs">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors
                  ${activeTab === tab.id
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Page content */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {activeTab === 'phase1' && (
          <Phase1 onJobId={(id) => setJobId(id)} />
        )}
        {activeTab === 'phase2' && (
          <Phase2 jobId={jobId} />
        )}
      </main>
    </div>
  )
}
