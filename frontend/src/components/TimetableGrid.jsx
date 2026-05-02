const CELL_COLORS = [
  'bg-blue-100 text-blue-800 border-blue-200',
  'bg-purple-100 text-purple-800 border-purple-200',
  'bg-emerald-100 text-emerald-800 border-emerald-200',
  'bg-orange-100 text-orange-800 border-orange-200',
  'bg-pink-100 text-pink-800 border-pink-200',
  'bg-teal-100 text-teal-800 border-teal-200',
]

function colorForProf(prof, profList) {
  const idx = profList.indexOf(prof)
  return CELL_COLORS[idx % CELL_COLORS.length]
}

export default function TimetableGrid({ schedule = [] }) {
  if (schedule.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 rounded-lg border border-dashed border-gray-300 bg-gray-50">
        <p className="text-gray-400 text-sm">No schedule yet</p>
      </div>
    )
  }

  // Collect unique timeslots (preserve order as they appear) and rooms
  const timeslotOrder = []
  const timeslotSet = new Set()
  const roomSet = new Set()

  for (const entry of schedule) {
    if (!timeslotSet.has(entry.timeslot)) {
      timeslotSet.add(entry.timeslot)
      timeslotOrder.push(entry.timeslot)
    }
    roomSet.add(entry.room)
  }

  const timeslots = timeslotOrder
  const rooms = Array.from(roomSet).sort()
  const professors = [...new Set(schedule.map((e) => e.professor))]

  // Build lookup: timeslot+room -> entry
  const lookup = {}
  for (const entry of schedule) {
    lookup[`${entry.timeslot}|${entry.room}`] = entry
  }

  return (
    <div className="overflow-auto rounded-lg border border-gray-200 shadow-sm">
      <table className="border-collapse text-xs min-w-max">
        <thead>
          <tr>
            <th className="sticky left-0 z-10 bg-gray-100 border border-gray-200 px-3 py-2 text-left text-gray-600 font-semibold whitespace-nowrap min-w-[140px]">
              Timeslot
            </th>
            {rooms.map((room) => (
              <th
                key={room}
                className="bg-gray-100 border border-gray-200 px-3 py-2 text-center text-gray-600 font-semibold whitespace-nowrap min-w-[120px]"
              >
                {room}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {timeslots.map((ts, rowIdx) => (
            <tr key={ts} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
              <td className="sticky left-0 z-10 border border-gray-200 px-3 py-2 font-medium text-gray-700 whitespace-nowrap bg-inherit">
                {ts}
              </td>
              {rooms.map((room) => {
                const entry = lookup[`${ts}|${room}`]
                if (!entry) {
                  return (
                    <td
                      key={room}
                      className="border border-gray-100 px-2 py-2 bg-gray-50"
                    />
                  )
                }
                const color = colorForProf(entry.professor, professors)
                const lastName = entry.professor.split(' ').pop()
                return (
                  <td key={room} className="border border-gray-200 px-2 py-2">
                    <div
                      className={`rounded border px-2 py-1 text-center leading-tight ${color}`}
                    >
                      <div className="font-semibold">
                        {entry.course}
                        {entry.section ? `-${entry.section}` : ''}
                      </div>
                      <div className="opacity-80">{lastName}</div>
                    </div>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
