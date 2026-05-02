import { useState, useEffect } from 'react'
import FileUpload from '../components/FileUpload.jsx'
import SolverStatus from '../components/SolverStatus.jsx'
import TimetableGrid from '../components/TimetableGrid.jsx'
import { uploadRooms, solvePhase2, downloadResult } from '../api.js'

export default function Phase2({ jobId: jobIdProp }) {
  const [roomsUploaded, setRoomsUploaded] = useState(false)
  const [solverStatus, setSolverStatus] = useState('idle')
  const [schedule, setSchedule] = useState([])
  const [unscheduled, setUnscheduled] = useState([])
  const [error, setError] = useState(null)
  const [downloading, setDownloading] = useState(null)
  const [resultJobId, setResultJobId] = useState(null)

  // Resolve job id: prop > localStorage
  const jobId = jobIdProp ?? localStorage.getItem('phase1_job_id') ?? null

  const canSolve = roomsUploaded && !!jobId && solverStatus !== 'running'

  async function handleSolve() {
    setError(null)
    setSolverStatus('running')
    setSchedule([])
    setUnscheduled([])
    try {
      const result = await solvePhase2(jobId)
      if (result.status === 'optimal' || result.status === 'Optimal') {
        setSolverStatus('optimal')
        setSchedule(result.schedule ?? [])
        setUnscheduled(result.unscheduled ?? [])
        setResultJobId(result.job_id ?? jobId)
      } else {
        setSolverStatus('infeasible')
        setError(result.message || 'Solver returned infeasible status.')
      }
    } catch (err) {
      setSolverStatus('infeasible')
      setError(err.message)
    }
  }

  async function handleDownload() {
    if (!resultJobId) return
    setDownloading(true)
    try {
      await downloadResult(resultJobId)
    } catch (err) {
      setError(`Download failed: ${err.message}`)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-800 mb-1">Phase 2 — Room &amp; Time Assignment</h2>
        <p className="text-sm text-gray-500">
          Upload the rooms file, then schedule Phase 1 assignments into rooms and time slots.
        </p>
      </div>

      {/* Job ID indicator */}
      <div className="flex items-center gap-2 text-sm">
        <span className="text-gray-500">Phase 1 Job ID:</span>
        {jobId ? (
          <code className="bg-gray-100 rounded px-2 py-0.5 text-gray-700 font-mono text-xs">{jobId}</code>
        ) : (
          <span className="text-red-500 text-xs">Not found — complete Phase 1 first</span>
        )}
      </div>

      {/* Upload */}
      <div className="max-w-xs">
        <FileUpload
          label="Rooms (.xlsx)"
          onUpload={async (file) => {
            await uploadRooms(file)
            setRoomsUploaded(true)
          }}
        />
      </div>

      {/* Solve row */}
      <div className="flex items-center gap-4 flex-wrap">
        <button
          onClick={handleSolve}
          disabled={!canSolve}
          className={`px-5 py-2 rounded-lg text-sm font-semibold transition-colors
            ${canSolve
              ? 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800'
              : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}
        >
          Solve Phase 2
        </button>
        <SolverStatus status={solverStatus} />
        {!jobId && (
          <span className="text-xs text-red-400">Complete Phase 1 to get a job ID</span>
        )}
        {jobId && !roomsUploaded && (
          <span className="text-xs text-gray-400">Upload rooms file to enable</span>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Download button */}
      {resultJobId && solverStatus === 'optimal' && (
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-emerald-600 text-white hover:bg-emerald-700 active:bg-emerald-800 transition-colors disabled:opacity-60"
        >
          <svg
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            />
          </svg>
          {downloading ? 'Downloading...' : 'Download Schedule (.xlsx)'}
        </button>
      )}

      {/* Timetable grid */}
      {schedule.length > 0 && (
        <div className="space-y-3">
          <h3 className="font-semibold text-gray-700">
            Timetable{' '}
            <span className="text-gray-400 font-normal text-sm">({schedule.length} sections scheduled)</span>
          </h3>
          <TimetableGrid schedule={schedule} />
        </div>
      )}

      {/* Unscheduled */}
      {unscheduled.length > 0 && (
        <div className="rounded-lg bg-yellow-50 border border-yellow-200 px-4 py-3">
          <p className="text-sm font-semibold text-yellow-800 mb-2">
            Unscheduled courses ({unscheduled.length})
          </p>
          <ul className="list-disc list-inside text-sm text-yellow-700 space-y-0.5">
            {unscheduled.map((c, i) => (
              <li key={i}>{typeof c === 'string' ? c : JSON.stringify(c)}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
