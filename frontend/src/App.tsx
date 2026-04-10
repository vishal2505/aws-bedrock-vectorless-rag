import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import Header        from './components/Header'
import UploadPanel   from './components/UploadPanel'
import DocumentList  from './components/DocumentList'
import QueryPanel    from './components/QueryPanel'
import SettingsModal from './components/SettingsModal'
import Toaster       from './components/Toaster'
import { fetchDocuments, getApiBase } from './api'
import type { Document, Toast } from './types'

let _toastId = 0

export default function App() {
  const [documents,      setDocuments]     = useState<Document[]>([])
  const [selectedDoc,    setSelectedDoc]   = useState<Document | null>(null)
  const [isLoadingDocs,  setIsLoadingDocs] = useState(false)
  const [settingsOpen,   setSettingsOpen]  = useState(false)
  const [toasts,         setToasts]        = useState<Toast[]>([])

  const addToast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const id = String(++_toastId)
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4500)
  }, [])

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const loadDocuments = useCallback(async () => {
    if (!getApiBase()) return
    setIsLoadingDocs(true)
    try {
      const docs = await fetchDocuments()
      setDocuments(docs)
      // Auto-select the first document if none is selected yet
      if (docs.length > 0) {
        setSelectedDoc((prev) => prev ?? docs[0])
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      addToast(`Could not load documents: ${msg}`, 'error')
    } finally {
      setIsLoadingDocs(false)
    }
  }, [addToast])

  // Show settings modal if no API URL on first visit
  useEffect(() => {
    if (!getApiBase()) {
      setTimeout(() => setSettingsOpen(true), 600)
    } else {
      loadDocuments()
    }
  }, [loadDocuments])

  const handleDocumentIndexed = (doc: Document) => {
    setDocuments((prev) => {
      const exists = prev.find((d) => d.doc_id === doc.doc_id)
      return exists ? prev.map((d) => d.doc_id === doc.doc_id ? doc : d) : [doc, ...prev]
    })
    setSelectedDoc(doc)
  }

  const handleSettingsSave = (url: string) => {
    void url
    loadDocuments()
  }

  return (
    <div className="flex flex-col min-h-screen bg-slate-950 bg-gradient-mesh">

      {/* Animated background orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none -z-10" aria-hidden>
        <div className="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full
          bg-gradient-radial from-indigo-600/12 to-transparent blur-3xl animate-float" />
        <div className="absolute top-[10%] right-[-15%] w-[500px] h-[500px] rounded-full
          bg-gradient-radial from-violet-600/10 to-transparent blur-3xl animate-float-delayed" />
        <div className="absolute bottom-[-10%] left-[20%] w-[500px] h-[500px] rounded-full
          bg-gradient-radial from-purple-700/10 to-transparent blur-3xl animate-float-slow" />
        <div className="absolute top-[40%] right-[10%] w-[300px] h-[300px] rounded-full
          bg-gradient-radial from-cyan-600/8 to-transparent blur-3xl animate-float" />
      </div>

      <Header onSettingsClick={() => setSettingsOpen(true)} />

      <main className="flex-1 max-w-[1400px] w-full mx-auto px-4 py-6 flex gap-5">

        {/* ── Left panel ── */}
        <motion.aside
          className="w-[340px] flex-shrink-0 flex flex-col gap-4"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
        >
          {/* Upload card */}
          <div className="glass rounded-2xl shadow-2xl shadow-black/30 overflow-hidden">
            <div className="px-5 pt-4 pb-2 border-b border-white/[0.05]">
              <h2 className="text-xs font-bold uppercase tracking-widest text-slate-500">
                Upload Document
              </h2>
            </div>
            <div className="p-4">
              <UploadPanel
                onDocumentIndexed={handleDocumentIndexed}
                onToast={addToast}
              />
            </div>
          </div>

          {/* Documents card */}
          <div className="glass rounded-2xl shadow-2xl shadow-black/30 overflow-hidden flex-1">
            <div className="p-4 h-full">
              <DocumentList
                documents={documents}
                selectedDocId={selectedDoc?.doc_id ?? null}
                isLoading={isLoadingDocs}
                onSelect={setSelectedDoc}
                onRefresh={loadDocuments}
              />
            </div>
          </div>
        </motion.aside>

        {/* ── Right panel ── */}
        <motion.section
          className="flex-1 glass rounded-2xl shadow-2xl shadow-black/30 overflow-hidden
            flex flex-col"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <div className="px-5 pt-4 pb-2 border-b border-white/[0.05] flex-shrink-0">
            <h2 className="text-xs font-bold uppercase tracking-widest text-slate-500">
              Ask a Question
            </h2>
          </div>
          <div className="flex-1 flex flex-col p-5 min-h-0 overflow-hidden">
            <QueryPanel
              selectedDoc={selectedDoc}
              onToast={addToast}
            />
          </div>
        </motion.section>

      </main>

      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSave={handleSettingsSave}
      />

      <Toaster toasts={toasts} onRemove={removeToast} />
    </div>
  )
}
