import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FileText, FileType2, RefreshCw, Inbox, Trash2, Loader2 } from 'lucide-react'
import { cn } from '../lib/utils'
import type { Document } from '../types'

interface Props {
  documents:      Document[]
  selectedDocId:  string | null
  isLoading:      boolean
  onSelect:       (doc: Document) => void
  onRefresh:      () => void
  onDelete:       (doc: Document) => Promise<void>
}

function DocIcon({ s3Key }: { s3Key: string }) {
  const isPdf = s3Key?.toLowerCase().includes('.pdf')
  return isPdf
    ? <FileType2 size={16} className="text-rose-400 flex-shrink-0" />
    : <FileText  size={16} className="text-indigo-400 flex-shrink-0" />
}

export default function DocumentList({
  documents, selectedDocId, isLoading, onSelect, onRefresh, onDelete,
}: Props) {
  const [deletingId, setDeletingId]   = useState<string | null>(null)
  const [confirmId,  setConfirmId]    = useState<string | null>(null)

  const handleDeleteClick = (e: React.MouseEvent, doc: Document) => {
    e.stopPropagation()
    setConfirmId(doc.doc_id)
  }

  const handleConfirmDelete = async (e: React.MouseEvent, doc: Document) => {
    e.stopPropagation()
    setConfirmId(null)
    setDeletingId(doc.doc_id)
    try {
      await onDelete(doc)
    } finally {
      setDeletingId(null)
    }
  }

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    setConfirmId(null)
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Header row */}
      <div className="flex items-center justify-between px-1">
        <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
          Indexed Documents
        </span>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="p-1.5 rounded-lg glass glass-hover text-slate-500 hover:text-slate-300
            transition-colors disabled:opacity-40"
          title="Refresh"
        >
          <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Loading skeletons */}
      {isLoading && (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-14 rounded-xl shimmer-bg" />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && documents.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex flex-col items-center gap-2 py-8 text-center"
        >
          <div className="w-12 h-12 rounded-2xl glass flex items-center justify-center">
            <Inbox size={20} className="text-slate-600" />
          </div>
          <p className="text-sm text-slate-500">No documents indexed yet</p>
          <p className="text-xs text-slate-600">Upload one above to get started</p>
        </motion.div>
      )}

      {/* Document list */}
      <AnimatePresence>
        {!isLoading && documents.map((doc, i) => {
          const filename   = doc.s3_key?.split('/').pop() ?? doc.doc_id
          const isSelected = doc.doc_id === selectedDocId
          const isDeleting = deletingId === doc.doc_id
          const isConfirm  = confirmId  === doc.doc_id

          return (
            <motion.div
              key={doc.doc_id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: isDeleting ? 0.4 : 1, x: 0 }}
              exit={{ opacity: 0, x: -20, height: 0, marginBottom: 0 }}
              transition={{ delay: i * 0.04 }}
              className="relative"
            >
              {/* Confirm-delete overlay */}
              <AnimatePresence>
                {isConfirm && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-0 z-10 flex items-center justify-between gap-2
                      px-3.5 rounded-xl bg-rose-950/80 border border-rose-500/30 backdrop-blur-sm"
                  >
                    <span className="text-xs text-rose-300 font-medium truncate">
                      Delete "{doc.doc_id}"?
                    </span>
                    <div className="flex gap-1.5 flex-shrink-0">
                      <button
                        onClick={(e) => handleConfirmDelete(e, doc)}
                        className="px-2.5 py-1 rounded-lg text-xs font-semibold
                          bg-rose-500 hover:bg-rose-400 text-white transition-colors"
                      >
                        Delete
                      </button>
                      <button
                        onClick={handleCancelDelete}
                        className="px-2.5 py-1 rounded-lg text-xs font-semibold
                          glass glass-hover text-slate-300 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Document row */}
              <button
                onClick={() => !isDeleting && onSelect(doc)}
                disabled={isDeleting}
                className={cn(
                  'w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-left',
                  'transition-all duration-200 group',
                  isSelected
                    ? 'glow-border bg-indigo-500/10'
                    : 'glass glass-hover',
                  isDeleting && 'pointer-events-none',
                )}
              >
                <div className={cn(
                  'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors',
                  isSelected
                    ? 'bg-indigo-500/20'
                    : 'bg-white/[0.04] group-hover:bg-white/[0.08]',
                )}>
                  <DocIcon s3Key={doc.s3_key} />
                </div>

                <div className="flex-1 min-w-0">
                  <p className={cn(
                    'text-sm font-medium truncate transition-colors',
                    isSelected ? 'text-indigo-300' : 'text-slate-200',
                  )}>
                    {doc.doc_id}
                  </p>
                  <p className="text-xs text-slate-500 truncate mt-0.5">
                    {doc.node_count} sections · {filename}
                  </p>
                </div>

                {/* Delete / loading icon — shown on hover or while deleting */}
                <div className="flex-shrink-0">
                  {isDeleting ? (
                    <Loader2 size={14} className="animate-spin text-rose-400" />
                  ) : (
                    <button
                      onClick={(e) => handleDeleteClick(e, doc)}
                      className={cn(
                        'p-1 rounded-md transition-all',
                        'opacity-0 group-hover:opacity-100',
                        'text-slate-600 hover:text-rose-400 hover:bg-rose-500/10',
                      )}
                      title="Delete document index"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>

                {isSelected && !isDeleting && (
                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 flex-shrink-0
                    shadow-[0_0_6px_rgba(99,102,241,0.8)]" />
                )}
              </button>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
