import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, XCircle, Info, X } from 'lucide-react'
import type { Toast } from '../types'

interface Props {
  toasts: Toast[]
  onRemove: (id: string) => void
}

const icons = {
  success: <CheckCircle2 size={16} className="text-emerald-400 flex-shrink-0" />,
  error:   <XCircle     size={16} className="text-rose-400    flex-shrink-0" />,
  info:    <Info        size={16} className="text-indigo-400  flex-shrink-0" />,
}

const borders = {
  success: 'border-emerald-500/30',
  error:   'border-rose-500/30',
  info:    'border-indigo-500/30',
}

export default function Toaster({ toasts, onRemove }: Props) {
  return (
    <div className="fixed top-20 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, x: 60, scale: 0.92 }}
            animate={{ opacity: 1, x: 0,  scale: 1 }}
            exit={{    opacity: 0, x: 60, scale: 0.92 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            className={`
              pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl
              bg-slate-900/90 backdrop-blur-2xl border ${borders[t.type]}
              shadow-2xl shadow-black/40 max-w-sm
            `}
          >
            {icons[t.type]}
            <span className="text-sm text-slate-200 leading-snug flex-1">{t.message}</span>
            <button
              onClick={() => onRemove(t.id)}
              className="text-slate-500 hover:text-slate-300 transition-colors ml-1"
            >
              <X size={14} />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
