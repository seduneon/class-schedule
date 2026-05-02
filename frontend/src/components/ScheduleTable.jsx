import { useState } from 'react'

const COLUMNS = [
  { key: 'professor', label: 'Professor' },
  { key: 'course', label: 'Course' },
  { key: 'section', label: 'Section' },
  { key: 'capacity', label: 'Capacity' },
  { key: 'ranking', label: 'Ranking' },
]

export default function ScheduleTable({ assignments = [] }) {
  const [sortKey, setSortKey] = useState('professor')
  const [sortDir, setSortDir] = useState('asc')

  function handleSort(key) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const sorted = [...assignments].sort((a, b) => {
    const av = a[sortKey] ?? ''
    const bv = b[sortKey] ?? ''
    const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true })
    return sortDir === 'asc' ? cmp : -cmp
  })

  if (assignments.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 rounded-lg border border-dashed border-gray-300 bg-gray-50">
        <p className="text-gray-400 text-sm">No assignments yet</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                className="px-4 py-3 text-left font-semibold text-gray-600 cursor-pointer select-none hover:bg-gray-100 whitespace-nowrap"
              >
                <span className="flex items-center gap-1">
                  {col.label}
                  {sortKey === col.key ? (
                    <span className="text-blue-500">{sortDir === 'asc' ? '↑' : '↓'}</span>
                  ) : (
                    <span className="text-gray-300">↕</span>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {sorted.map((row, i) => (
            <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
              <td className="px-4 py-2.5 font-medium text-gray-800">{row.professor}</td>
              <td className="px-4 py-2.5 text-gray-700">{row.course}</td>
              <td className="px-4 py-2.5 text-gray-600">{row.section}</td>
              <td className="px-4 py-2.5 text-gray-600">{row.capacity}</td>
              <td className="px-4 py-2.5 text-gray-600">{row.ranking}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
