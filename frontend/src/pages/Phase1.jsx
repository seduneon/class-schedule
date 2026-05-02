import { useState } from 'react'
import FileUpload from '../components/FileUpload.jsx'
import SolverStatus from '../components/SolverStatus.jsx'
import ScheduleTable from '../components/ScheduleTable.jsx'
import {
  uploadProfessors,
  uploadCourses,
  uploadPreferences,
  solvePhase1,
} from '../api.js'

export default function Phase1({ onJobId }) {
  const [uploaded, setUploaded] = useState({
    professors: false,
    courses: false,
    preferences: false,
  })
  const [solverStatus, setSolverStatus] = useState('idle')
  const [assignments, setAssignments] = useState([])
  const [unassigned, setUnassigned] = useState([])
  const [error, setError] = useState(null)

  function markUploaded(key) {
    setUploaded((prev) => ({ ...prev, [key]: true }))
  }

  const allUploaded = uploaded.professors && uploaded.courses && uploaded.preferences
  const canSolve = allUploaded && solverStatus !== 'running'

  async function handleSolve() {
    setError(null)
    setSolverStatus('running')
    setAssignments([])
    setUnassigned([])
    try {
      const result = await solvePhase1()
      if (result.status === 'optimal' || result.status === 'Optimal') {
        setSolverStatus('optimal')
        setAssignments(result.assignments ?? [])
        setUnassigned(result.unassigned ?? [])
        if (result.job_id) {
          localStorage.setItem('phase1_job_id', result.job_id)
          onJobId?.(result.job_id)
        }
      } else {
        setSolverStatus('infeasible')
        setError(result.message || 'Solver returned infeasible status.')
      }
    } catch (err) {
      setSolverStatus('infeasible')
      setError(err.message)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-800 mb-1">Phase 1 — Professor Assignment</h2>
        <p className="text-sm text-gray-500">
          Upload the three input files, then run the ILP solver to assign professors to course sections.
        </p>
      </div>

      {/* Upload section */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <FileUpload
          label="Professors (.xlsx)"
          onUpload={async (file) => {
            await uploadProfessors(file)
            markUploaded('professors')
          }}
        />
        <FileUpload
          label="Courses (.xlsx)"
          onUpload={async (file) => {
            await uploadCourses(file)
            markUploaded('courses')
          }}
        />
        <FileUpload
          label="Preferences (.xlsx)"
          onUpload={async (file) => {
            await uploadPreferences(file)
            markUploaded('preferences')
          }}
        />
      </div>

      {/* Solve row */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleSolve}
          disabled={!canSolve}
          className={`px-5 py-2 rounded-lg text-sm font-semibold transition-colors
            ${canSolve
              ? 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800'
              : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}
        >
          Solve Phase 1
        </button>
        <SolverStatus status={solverStatus} />
        {!allUploaded && (
          <span className="text-xs text-gray-400">Upload all 3 files to enable</span>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Results */}
      {assignments.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-700">
              Assignments{' '}
              <span className="text-gray-400 font-normal text-sm">({assignments.length})</span>
            </h3>
          </div>
          <ScheduleTable assignments={assignments} />
        </div>
      )}

      {/* Unassigned */}
      {unassigned.length > 0 && (
        <div className="rounded-lg bg-yellow-50 border border-yellow-200 px-4 py-3">
          <p className="text-sm font-semibold text-yellow-800 mb-2">
            Unassigned professors ({unassigned.length})
          </p>
          <ul className="list-disc list-inside text-sm text-yellow-700 space-y-0.5">
            {unassigned.map((p, i) => (
              <li key={i}>{typeof p === 'string' ? p : JSON.stringify(p)}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
