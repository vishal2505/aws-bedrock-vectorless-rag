import type { Document, QueryResult, PresignResult } from './types'

/** Resolve API base URL: config.js → env var → localStorage → empty */
export function getApiBase(): string {
  return (
    (window as unknown as { RAG_API_URL?: string }).RAG_API_URL ||
    (import.meta.env.VITE_API_URL as string | undefined) ||
    localStorage.getItem('rag_api_url') ||
    ''
  )
}

export function saveApiBase(url: string) {
  localStorage.setItem('rag_api_url', url.replace(/\/$/, ''))
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const base = getApiBase()
  if (!base) throw new Error('API URL not configured. Click ⚙ to set it.')
  const url = base.replace(/\/$/, '') + path
  const res = await fetch(url, { ...options })
  const data = await res.json()
  if (!res.ok) throw new Error((data as { error?: string }).error ?? `HTTP ${res.status}`)
  return data as T
}

export async function fetchDocuments(): Promise<Document[]> {
  const data = await apiFetch<{ documents: Document[] }>('/documents')
  return data.documents
}

export async function getPresignedUrl(
  filename: string,
  contentType: string,
): Promise<PresignResult> {
  return apiFetch<PresignResult>('/presign', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, content_type: contentType }),
  })
}

/** Upload directly to S3 via presigned URL with progress callback */
export function uploadToS3(
  presignedUrl: string,
  file: File,
  onProgress: (pct: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', presignedUrl)
    xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream')
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`S3 upload failed: ${xhr.status}`)))
    xhr.onerror = () => reject(new Error('S3 upload network error'))
    xhr.send(file)
  })
}

export interface IngestResponse {
  doc_id: string
  status: 'processing' | 'indexed'
  node_count?: number   // present only when status === 'indexed' (local dev)
}

export async function ingestDocument(
  s3Key: string,
  docId: string,
): Promise<IngestResponse> {
  const base = getApiBase()
  if (!base) throw new Error('API URL not configured. Click ⚙ to set it.')
  const res = await fetch(`${base.replace(/\/$/, '')}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ s3_key: s3Key, doc_id: docId }),
  })
  const data = await res.json()
  // 202 = async processing started (AWS), 200 = done synchronously (local dev)
  if (res.status !== 200 && res.status !== 202) {
    throw new Error((data as { error?: string }).error ?? `HTTP ${res.status}`)
  }
  return data as IngestResponse
}

/** Poll GET /documents every 3 s until doc_id appears, or timeout after maxMs. */
export async function pollUntilIndexed(
  docId: string,
  onAttempt?: (attempt: number) => void,
  maxMs = 5 * 60 * 1000,
): Promise<Document> {
  const interval = 3000
  const maxAttempts = Math.ceil(maxMs / interval)
  for (let i = 1; i <= maxAttempts; i++) {
    await new Promise(r => setTimeout(r, interval))
    onAttempt?.(i)
    const docs = await fetchDocuments()
    const found = docs.find(d => d.doc_id === docId)
    if (found) return found
  }
  throw new Error('Indexing timed out after 5 minutes. Check Lambda logs for errors.')
}

export async function deleteDocument(docId: string): Promise<{ doc_id: string; deleted_items: number }> {
  return apiFetch(`/documents/${encodeURIComponent(docId)}`, { method: 'DELETE' })
}

export async function queryDocument(
  docId: string,
  question: string,
): Promise<QueryResult> {
  return apiFetch('/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ doc_id: docId, question }),
  })
}
