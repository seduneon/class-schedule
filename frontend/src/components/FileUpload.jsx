import { useState, useRef } from 'react'

export default function FileUpload({ label, onUpload }) {
  const [fileName, setFileName] = useState(null)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const inputRef = useRef(null)

  async function handleFile(file) {
    if (!file) return
    setError(null)
    setUploading(true)
    try {
      await onUpload(file)
      setFileName(file.name)
    } catch (err) {
      setError(err.message)
      setFileName(null)
    } finally {
      setUploading(false)
    }
  }

  function onInputChange(e) {
    handleFile(e.target.files[0])
  }

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  function onDragOver(e) {
    e.preventDefault()
    setDragging(true)
  }

  function onDragLeave() {
    setDragging(false)
  }

  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm font-medium text-gray-700">{label}</span>
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        className={`relative flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 cursor-pointer transition-colors
          ${dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50 hover:border-blue-400 hover:bg-blue-50'}
          ${uploading ? 'opacity-60 pointer-events-none' : ''}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls"
          className="hidden"
          onChange={onInputChange}
        />
        {uploading ? (
          <svg
            className="animate-spin h-6 w-6 text-blue-500"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
        ) : (
          <svg
            className="h-8 w-8 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
            />
          </svg>
        )}

        {fileName ? (
          <p className="text-sm text-green-700 font-medium text-center break-all">{fileName}</p>
        ) : (
          <p className="text-sm text-gray-500 text-center">
            Drag &amp; drop or <span className="text-blue-600 underline">browse</span>
            <br />
            <span className="text-xs text-gray-400">.xlsx / .xls</span>
          </p>
        )}
      </div>

      {error && (
        <p className="text-xs text-red-600 mt-0.5">{error}</p>
      )}
    </div>
  )
}
