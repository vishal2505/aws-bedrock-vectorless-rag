import { useState } from 'react'
import { motion } from 'framer-motion'
import { Sparkles, ChevronDown, ChevronUp, BookOpen } from 'lucide-react'
import { useTypewriter } from '../hooks/useTypewriter'
import type { QueryResult } from '../types'

interface Props {
  result: QueryResult
}

export default function AnswerCard({ result }: Props) {
  const [excerptOpen, setExcerptOpen] = useState(false)
  const displayed = useTypewriter(result.answer, 10)

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.98 }}
      animate={{ opacity: 1, y: 0,  scale: 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 28 }}
      className="space-y-3"
    >
      {/* Main answer */}
      <div className="relative rounded-2xl overflow-hidden">
        {/* Gradient border via pseudo-element */}
        <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-indigo-500/20 via-violet-500/10 to-purple-500/20 p-px">
          <div className="w-full h-full rounded-2xl bg-slate-950" />
        </div>

        <div className="relative p-5 space-y-3">
          {/* Label */}
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600
              flex items-center justify-center shadow-lg shadow-indigo-500/30">
              <Sparkles size={12} className="text-white" />
            </div>
            <span className="text-[11px] font-bold uppercase tracking-widest text-gradient">
              Answer
            </span>
          </div>

          {/* Answer text with typewriter */}
          <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
            {displayed}
            {/* Blinking cursor while typing */}
            {displayed.length < result.answer.length && (
              <span className="inline-block w-0.5 h-4 bg-indigo-400 ml-0.5 animate-pulse" />
            )}
          </p>
        </div>
      </div>

      {/* Source nodes */}
      {result.used_node_ids?.length > 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="px-4 py-3 rounded-xl glass space-y-2"
        >
          <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
            Sections Used
          </p>
          <div className="flex flex-wrap gap-1.5">
            {result.used_node_ids.map((id) => (
              <span key={id} className="node-badge">{id}</span>
            ))}
          </div>
        </motion.div>
      )}

      {/* Context excerpt (collapsible) */}
      {result.raw_context_excerpt && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="rounded-xl glass overflow-hidden"
        >
          <button
            onClick={() => setExcerptOpen((p) => !p)}
            className="w-full flex items-center justify-between px-4 py-3
              text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
          >
            <span className="flex items-center gap-2">
              <BookOpen size={13} />
              Context excerpt
            </span>
            {excerptOpen
              ? <ChevronUp size={13} />
              : <ChevronDown size={13} />
            }
          </button>

          <motion.div
            initial={false}
            animate={{ height: excerptOpen ? 'auto' : 0, opacity: excerptOpen ? 1 : 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4">
              <div className="border-l-2 border-indigo-500/40 pl-3">
                <p className="text-xs text-slate-400 leading-relaxed italic">
                  "{result.raw_context_excerpt}"
                </p>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </motion.div>
  )
}
