import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Link2, CheckCircle2 } from 'lucide-react'
import { cn } from '../lib/utils'
import { getApiBase, saveApiBase } from '../api'

interface Props {
  isOpen:  boolean
  onClose: () => void
  onSave:  (url: string) => void
}

export default function SettingsModal({ isOpen, onClose, onSave }: Props) {
  const [url, setUrl] = useState(getApiBase)
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    const trimmed = url.trim().replace(/\/$/, '')
    if (!trimmed) return
    saveApiBase(trimmed)
    setSaved(true)
    onSave(trimmed)
    setTimeout(() => { setSaved(false); onClose() }, 800)
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Modal */}
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="pointer-events-auto w-full max-w-md glass rounded-2xl shadow-2xl
                shadow-black/60 overflow-hidden"
              initial={{ scale: 0.93, y: 20 }}
              animate={{ scale: 1,    y: 0  }}
              exit={{    scale: 0.93, y: 20 }}
              transition={{ type: 'spring', stiffness: 350, damping: 30 }}
            >
              {/* Header */}
              <div className="flex items-center justify-between px-6 pt-6 pb-4
                border-b border-white/[0.06]">
                <div>
                  <h2 className="text-base font-bold text-white">API Configuration</h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Paste the <code className="font-mono text-indigo-400">api_base_url</code> from Terraform output
                  </p>
                </div>
                <button
                  onClick={onClose}
                  className="w-8 h-8 rounded-lg glass glass-hover flex items-center justify-center
                    text-slate-400 hover:text-white transition-colors"
                >
                  <X size={15} />
                </button>
              </div>

              {/* Body */}
              <div className="px-6 py-5 space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-2">
                    API Base URL
                  </label>
                  <div className="relative">
                    <Link2 size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                    <input
                      type="url"
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSave()}
                      placeholder="https://xxxx.execute-api.ap-southeast-1.amazonaws.com/prod"
                      className={cn(
                        'w-full pl-9 pr-4 py-2.5 rounded-xl bg-white/[0.05] border text-sm',
                        'text-slate-200 placeholder:text-slate-600 outline-none transition-all',
                        'focus:bg-white/[0.08] focus:border-indigo-500/60',
                        'focus:shadow-[0_0_0_3px_rgba(99,102,241,0.12)]',
                        url ? 'border-white/[0.12]' : 'border-white/[0.06]',
                      )}
                      autoFocus
                    />
                  </div>
                  <p className="mt-2 text-[11px] text-slate-500">
                    For local dev: <code className="font-mono text-slate-400">http://localhost:8000</code>
                  </p>
                </div>
              </div>

              {/* Footer */}
              <div className="flex gap-3 px-6 pb-6">
                <button
                  onClick={onClose}
                  className="flex-1 py-2.5 rounded-xl glass glass-hover text-sm font-medium
                    text-slate-300 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={!url.trim()}
                  className={cn(
                    'flex-1 py-2.5 rounded-xl text-sm font-semibold text-white',
                    'flex items-center justify-center gap-2',
                    saved ? 'bg-emerald-600' : 'btn-primary',
                    !url.trim() && 'opacity-40 cursor-not-allowed',
                  )}
                >
                  {saved
                    ? <><CheckCircle2 size={15} /> Saved!</>
                    : 'Save & Connect'
                  }
                </button>
              </div>
            </motion.div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
