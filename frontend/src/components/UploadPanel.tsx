import { useState, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, File, FileText, CheckCircle2, AlertCircle, X, Loader2 } from 'lucide-react'
import { cn, slugify } from '../lib/utils'
import { getPresignedUrl, uploadToS3, ingestDocument, pollUntilIndexed } from '../api'
import type { UploadStage, Document } from '../types'

interface Props {
  onDocumentIndexed: (doc: Document) => void
  onToast: (msg: string, type: 'success' | 'error' | 'info') => void
}

const STAGE_LABELS: Record<UploadStage, string> = {
  idle:      '',
  presigning:'Getting upload URL…',
  uploading: 'Uploading to S3…',
  indexing:  'Bedrock is indexing… this takes 30–90 s',
  done:      'Successfully indexed!',
  error:     '',
}

export default function UploadPanel({ onDocumentIndexed, onToast }: Props) {
  const [file, setFile]           = useState<File | null>(null)
  const [stage, setStage]           = useState<UploadStage>('idle')
  const [progress, setProgress]     = useState(0)
  const [pollCount, setPollCount]   = useState(0)
  const [error, setError]           = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const acceptFile = (f: File) => {
    setFile(f)
    setStage('idle')
    setError('')
    setProgress(0)
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) acceptFile(f)
  }, [])

  const handleUpload = async () => {
    if (!file) return
    setError('')
    setProgress(0)

    try {
      setStage('presigning')
      const { presigned_url, s3_key } = await getPresignedUrl(
        file.name,
        file.type || 'application/octet-stream',
      )

      setStage('uploading')
      await uploadToS3(presigned_url, file, setProgress)

      setStage('indexing')
      setPollCount(0)
      const docId = slugify(file.name)
      const result = await ingestDocument(s3_key, docId)

      let doc: Document
      if (result.status === 'processing') {
        // AWS path — Lambda is running async, poll until the doc appears
        doc = await pollUntilIndexed(docId, (n) => setPollCount(n))
      } else {
        // Local dev path — indexing finished synchronously
        doc = { doc_id: result.doc_id, s3_key, node_count: result.node_count ?? 0 }
      }

      setStage('done')
      onDocumentIndexed(doc)
      onToast(`"${doc.doc_id}" indexed with ${doc.node_count} sections`, 'success')

      // Reset after success
      setTimeout(() => { setFile(null); setStage('idle') }, 2500)

    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(msg)
      setStage('error')
      onToast(msg, 'error')
    }
  }

  const isActive = stage !== 'idle' && stage !== 'done' && stage !== 'error'
  const fileIcon = file?.name.endsWith('.pdf') ? (
    <File size={18} className="text-rose-400" />
  ) : (
    <FileText size={18} className="text-indigo-400" />
  )

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => !isActive && inputRef.current?.click()}
        className={cn(
          'relative rounded-2xl border-2 border-dashed transition-all duration-200 cursor-pointer',
          'flex flex-col items-center justify-center gap-2 py-8 px-4 text-center',
          isDragging
            ? 'border-indigo-500/70 bg-indigo-500/10 scale-[1.01]'
            : file
              ? 'border-indigo-500/40 bg-indigo-500/5'
              : 'border-white/[0.1] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.03]',
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.md,.markdown,.txt"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && acceptFile(e.target.files[0])}
        />

        <motion.div
          animate={isDragging ? { scale: 1.15, rotate: -5 } : { scale: 1, rotate: 0 }}
          className={cn(
            'w-12 h-12 rounded-2xl flex items-center justify-center',
            'bg-gradient-to-br',
            isDragging || file
              ? 'from-indigo-500/20 to-violet-500/20'
              : 'from-white/5 to-white/[0.02]',
          )}
        >
          <Upload size={20} className={isDragging ? 'text-indigo-400' : 'text-slate-500'} />
        </motion.div>

        <div>
          <p className="text-sm font-medium text-slate-300">
            {isDragging ? 'Drop it!' : 'Drop a file or click to browse'}
          </p>
          <p className="text-xs text-slate-600 mt-0.5">PDF, Markdown, or TXT</p>
        </div>
      </div>

      {/* Selected file */}
      <AnimatePresence>
        {file && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            className="flex items-center gap-3 px-4 py-3 rounded-xl glass"
          >
            {fileIcon}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-slate-200 truncate">{file.name}</p>
              <p className="text-xs text-slate-500">
                {(file.size / 1024).toFixed(0)} KB
              </p>
            </div>
            {stage === 'idle' && (
              <button
                onClick={(e) => { e.stopPropagation(); setFile(null); setStage('idle') }}
                className="text-slate-600 hover:text-slate-400 transition-colors"
              >
                <X size={15} />
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Progress bar (uploading) */}
      <AnimatePresence>
        {stage === 'uploading' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="space-y-1"
          >
            <div className="flex justify-between text-xs text-slate-500">
              <span>Uploading</span>
              <span>{progress}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500"
                initial={{ width: '0%' }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Status message */}
      <AnimatePresence>
        {stage !== 'idle' && stage !== 'error' && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={cn(
              'flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-sm',
              stage === 'done'
                ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
                : 'bg-indigo-500/10 border border-indigo-500/20 text-indigo-300',
            )}
          >
            {stage === 'done'
              ? <CheckCircle2 size={15} className="flex-shrink-0" />
              : <Loader2 size={15} className="animate-spin flex-shrink-0" />
            }
            <span>
              {stage === 'indexing' && pollCount > 0
                ? `Bedrock is indexing… (${pollCount * 3}s elapsed)`
                : STAGE_LABELS[stage]}
            </span>
          </motion.div>
        )}

        {stage === 'error' && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-start gap-2.5 px-4 py-2.5 rounded-xl text-sm
              bg-rose-500/10 border border-rose-500/20 text-rose-400"
          >
            <AlertCircle size={15} className="flex-shrink-0 mt-0.5" />
            <span className="break-words">{error}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Upload button */}
      <button
        onClick={handleUpload}
        disabled={!file || isActive}
        className={cn(
          'w-full py-3 rounded-xl text-sm font-semibold text-white',
          'flex items-center justify-center gap-2 btn-primary',
        )}
      >
        {isActive
          ? <><Loader2 size={15} className="animate-spin" /> Processing…</>
          : <><Upload size={15} /> Upload &amp; Index</>
        }
      </button>
    </div>
  )
}
