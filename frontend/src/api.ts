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

export async function ingestDocument(
  s3Key: string,
  docId: string,
): Promise<{ doc_id: string; node_count: number }> {
  return apiFetch('/ingest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ s3_key: s3Key, doc_id: docId }),
  })
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
