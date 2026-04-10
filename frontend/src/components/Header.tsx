import { Settings, Zap } from 'lucide-react'
import { motion } from 'framer-motion'

interface Props {
  onSettingsClick: () => void
}

export default function Header({ onSettingsClick }: Props) {
  return (
    <header className="sticky top-0 z-40 h-16 flex items-center px-6
      bg-slate-950/70 backdrop-blur-2xl border-b border-white/[0.06]">

      {/* Logo */}
      <motion.div
        className="flex items-center gap-3"
        initial={{ opacity: 0, x: -12 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="relative w-9 h-9 flex-shrink-0">
          {/* Glow ring */}
          <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600
            blur-sm opacity-60 animate-glow-pulse" />
          <div className="relative w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600
            flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <Zap size={18} className="text-white" strokeWidth={2.5} />
          </div>
        </div>

        <div>
          <h1 className="text-sm font-bold tracking-tight text-white leading-none">
            Vectorless RAG
          </h1>
          <p className="text-[11px] text-slate-400 mt-0.5 leading-none">
            PageIndex · Amazon Bedrock
          </p>
        </div>
      </motion.div>

      {/* Center badges */}
      <motion.div
        className="hidden sm:flex items-center gap-2 mx-auto"
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.15 }}
      >
        {['No Embeddings', 'No Vector DB', 'LLM-Driven Retrieval'].map((label) => (
          <span key={label}
            className="text-[11px] font-medium px-2.5 py-1 rounded-full
              bg-white/[0.05] border border-white/[0.08] text-slate-400">
            {label}
          </span>
        ))}
      </motion.div>

      {/* Settings */}
      <motion.button
        onClick={onSettingsClick}
        className="ml-auto w-9 h-9 rounded-xl glass glass-hover flex items-center justify-center
          text-slate-400 hover:text-white transition-colors"
        title="Configure API endpoint"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        <Settings size={16} />
      </motion.button>
    </header>
  )
}
