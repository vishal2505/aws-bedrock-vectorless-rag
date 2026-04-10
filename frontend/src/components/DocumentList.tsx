import { motion, AnimatePresence } from 'framer-motion'
import { FileText, FileType2, RefreshCw, Inbox } from 'lucide-react'
import { cn } from '../lib/utils'
import type { Document } from '../types'

interface Props {
  documents:      Document[]
  selectedDocId:  string | null
  isLoading:      boolean
  onSelect:       (doc: Document) => void
  onRefresh:      () => void
}

function DocIcon({ s3Key }: { s3Key: string }) {
  const isPdf = s3Key?.toLowerCase().includes('.pdf')
  return isPdf
    ? <FileType2 size={16} className="text-rose-400 flex-shrink-0" />
    : <FileText  size={16} className="text-indigo-400 flex-shrink-0" />
}

export default function DocumentList({
  documents, selectedDocId, isLoading, onSelect, onRefresh,
}: Props) {
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
          const filename = doc.s3_key?.split('/').pop() ?? doc.doc_id
          const isSelected = doc.doc_id === selectedDocId

          return (
            <motion.button
              key={doc.doc_id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.04 }}
              onClick={() => onSelect(doc)}
              className={cn(
                'w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-left',
                'transition-all duration-200 group',
                isSelected
                  ? 'glow-border bg-indigo-500/10'
                  : 'glass glass-hover',
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

              {isSelected && (
                <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 flex-shrink-0
                  shadow-[0_0_6px_rgba(99,102,241,0.8)]" />
              )}
            </motion.button>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
