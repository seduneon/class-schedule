const BASE_URL = 'http://localhost:8000'

export async function uploadFile(endpoint, file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `Upload failed: ${res.status}`)
  }
  return res.json()
}

export async function uploadProfessors(file) {
  return uploadFile('/upload/professors', file)
}

export async function uploadCourses(file) {
  return uploadFile('/upload/courses', file)
}

export async function uploadPreferences(file) {
  return uploadFile('/upload/preferences', file)
}

export async function uploadRooms(file) {
  return uploadFile('/upload/rooms', file)
}

export async function solvePhase1() {
  const res = await fetch(`${BASE_URL}/solve/phase1`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `Solve phase 1 failed: ${res.status}`)
  }
  return res.json()
}

export async function solvePhase2(jobId) {
  const res = await fetch(`${BASE_URL}/solve/phase2`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_id: jobId }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `Solve phase 2 failed: ${res.status}`)
  }
  return res.json()
}

export async function getResult(jobId) {
  const res = await fetch(`${BASE_URL}/results/${jobId}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `Get result failed: ${res.status}`)
  }
  return res.json()
}

export async function downloadResult(jobId) {
  const res = await fetch(`${BASE_URL}/results/download/${jobId}`)
  if (!res.ok) {
    throw new Error(`Download failed: ${res.status}`)
  }
  const blob = await res.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `schedule_${jobId}.xlsx`
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}
