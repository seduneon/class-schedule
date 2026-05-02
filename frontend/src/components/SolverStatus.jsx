export default function SolverStatus({ status = 'idle' }) {
  const configs = {
    idle: {
      label: 'Idle',
      classes: 'bg-gray-100 text-gray-600 border-gray-300',
      spinner: false,
    },
    running: {
      label: 'Running',
      classes: 'bg-yellow-100 text-yellow-700 border-yellow-400',
      spinner: true,
    },
    optimal: {
      label: 'Optimal',
      classes: 'bg-green-100 text-green-700 border-green-400',
      spinner: false,
    },
    infeasible: {
      label: 'Infeasible',
      classes: 'bg-red-100 text-red-700 border-red-400',
      spinner: false,
    },
  }

  const config = configs[status] ?? configs.idle

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-sm font-medium ${config.classes}`}
    >
      {config.spinner && (
        <svg
          className="animate-spin h-3.5 w-3.5"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v8H4z"
          />
        </svg>
      )}
      {config.label}
    </span>
  )
}
