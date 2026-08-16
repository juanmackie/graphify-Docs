import { useCallback, useRef, useState } from 'react'

interface Props {
  onUpload: (file: File, mode: 'fast' | 'balanced' | 'full') => Promise<void>
}

const ACCEPTED = '.pdf,.docx,.txt,.md,.pptx,.html,.htm'

export default function UploadPage({ onUpload }: Props) {
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState<'fast' | 'balanced' | 'full'>('balanced')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(
    async (file: File) => {
      setBusy(true)
      try {
        await onUpload(file, mode)
      } finally {
        setBusy(false)
      }
    },
    [mode, onUpload],
  )

  return (
    <section
      className={`card upload ${dragging ? 'dragging' : ''}`}
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        const f = e.dataTransfer.files?.[0]
        if (f) void handleFile(f)
      }}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) void handleFile(f)
          e.target.value = ''
        }}
      />
      <div className="upload-icon">[+]</div>
      <h2>{busy ? 'UPLOADING…' : dragging ? 'DROP IT' : 'UPLOAD BAY'}</h2>
      <p className="muted">
        PDF · DOCX · TXT · MD · PPTX · HTML — DROP FILE OR CLICK TO SELECT
      </p>
      <label className="upload-mode" onClick={(e) => e.stopPropagation()}>
        EXTRACTION MODE{' '}
        <select
          value={mode}
          disabled={busy}
          onChange={(e) => setMode(e.target.value as 'fast' | 'balanced' | 'full')}
        >
          <option value="fast">FAST · representative chunks</option>
          <option value="balanced">BALANCED · recommended</option>
          <option value="full">FULL · every chunk</option>
        </select>
      </label>
    </section>
  )
}
