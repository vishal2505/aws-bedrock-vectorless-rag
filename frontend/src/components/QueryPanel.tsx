import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, MessageSquare, Loader2, Bot } from 'lucide-react'
import { cn } from '../lib/utils'
import { queryDocument } from '../api'
import AnswerCard from './AnswerCard'
import type { Document, QueryResult } from '../types'

interface Props {
  selectedDoc: Document | null
  onToast: (msg: string, type: 'success' | 'error' | 'info') => void
}

const EXAMPLE_QUESTIONS = [
  'What is the main topic of this document?',
  'Summarise the key findings.',
  'What are the recommended next steps?',
  'What conclusions does the document reach?',
]

export default function QueryPanel({ selectedDoc, onToast }: Props) {
  const [question, setQuestion]   = useState('')
  const [isQuerying, setIsQuerying] = useState(false)
  const [result, setResult]       = useState<QueryResult | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const answerRef   = useRef<HTMLDivElement>(null)

  // Reset answer when doc changes
  useEffect(() => {
    setResult(null)
    setQuestion('')
  }, [selectedDoc?.doc_id])

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }, [question])

  // Scroll to answer
  useEffect(() => {
    if (result) answerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [result])

  const handleQuery = async () => {
    if (!selectedDoc || !question.trim() || isQuerying) return
    setIsQuerying(true)
    setResult(null)

    try {
      const data = await queryDocument(selectedDoc.doc_id, question.trim())
      setResult(data)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      onToast(msg, 'error')
    } finally {
      setIsQuerying(false)
    }
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleQuery()
    }
  }

  // ── No doc selected ──────────────────────────────────────────────
  if (!selectedDoc) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-16 text-center px-8">
        <motion.div
          animate={{ y: [0, -8, 0] }}
          transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
          className="w-16 h-16 rounded-2xl glass flex items-center justify-center mb-5
            shadow-inner-light"
        >
          <MessageSquare size={26} className="text-slate-500" />
        </motion.div>
        <h3 className="text-base font-semibold text-slate-300 mb-2">
          Select a document to begin
        </h3>
        <p className="text-sm text-slate-500 leading-relaxed max-w-xs">
          Choose an indexed document from the left panel, then ask any question about it.
        </p>

        <div className="mt-6 space-y-2 w-full max-w-xs">
          {EXAMPLE_QUESTIONS.map((q, i) => (
            <motion.div
              key={q}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + i * 0.08 }}
              className="px-4 py-2.5 rounded-xl glass text-xs text-slate-500 text-left"
            >
              {q}
            </motion.div>
          ))}
        </div>
      </div>
    )
  }

  // ── Doc selected ─────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full">

      {/* Doc badge */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-2.5 px-4 py-2.5 rounded-xl
          bg-indigo-500/10 border border-indigo-500/25 mb-4 flex-shrink-0"
      >
        <div className="w-6 h-6 rounded-lg bg-indigo-500/20 flex items-center justify-center">
          <Bot size={13} className="text-indigo-400" />
        </div>
        <div>
          <p className="text-xs font-semibold text-indigo-300">{selectedDoc.doc_id}</p>
          <p className="text-[11px] text-indigo-400/60">{selectedDoc.node_count} sections indexed</p>
        </div>
      </motion.div>

      {/* Answer area */}
      <div className="flex-1 overflow-y-auto space-y-3 min-h-0 pb-4">
        <AnimatePresence>
          {isQuerying && (
            <motion.div
              key="loading"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-3 px-4 py-3 rounded-xl
                bg-indigo-500/10 border border-indigo-500/20"
            >
              <Loader2 size={15} className="animate-spin text-indigo-400 flex-shrink-0" />
              <div>
                <p className="text-sm text-indigo-300 font-medium">Searching document tree…</p>
                <p className="text-xs text-indigo-400/60 mt-0.5">
                  Bedrock is reasoning over {selectedDoc.node_count} sections
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {result && (
          <div ref={answerRef}>
            <AnswerCard result={result} />
          </div>
        )}

        {!result && !isQuerying && (
          <div className="grid grid-cols-2 gap-2">
            {EXAMPLE_QUESTIONS.map((q, i) => (
              <motion.button
                key={q}
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.06 }}
                onClick={() => { setQuestion(q); textareaRef.current?.focus() }}
                className="px-3 py-2.5 rounded-xl glass glass-hover text-left
                  text-xs text-slate-400 hover:text-slate-200 transition-colors leading-snug"
              >
                {q}
              </motion.button>
            ))}
          </div>
        )}
      </div>

      {/* Input area */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="flex-shrink-0 mt-auto pt-3"
      >
        <div className={cn(
          'flex items-end gap-3 px-4 py-3 rounded-2xl transition-all duration-200',
          'bg-white/[0.04] border',
          question
            ? 'border-indigo-500/40 shadow-[0_0_0_3px_rgba(99,102,241,0.08)]'
            : 'border-white/[0.08]',
        )}>
          <textarea
            ref={textareaRef}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={isQuerying}
            rows={1}
            placeholder="Ask anything about this document… (Enter to send)"
            className="flex-1 bg-transparent resize-none outline-none text-sm text-slate-200
              placeholder:text-slate-600 leading-relaxed disabled:opacity-50"
          />
          <button
            onClick={handleQuery}
            disabled={!question.trim() || isQuerying}
            className={cn(
              'w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0',
              'transition-all duration-200',
              question.trim() && !isQuerying
                ? 'btn-primary text-white'
                : 'bg-white/[0.05] text-slate-600 cursor-not-allowed',
            )}
          >
            {isQuerying
              ? <Loader2 size={16} className="animate-spin" />
              : <Send size={15} />
            }
          </button>
        </div>
        <p className="text-[11px] text-slate-600 mt-1.5 text-center">
          Shift+Enter for new line · Enter to send
        </p>
      </motion.div>
    </div>
  )
}
