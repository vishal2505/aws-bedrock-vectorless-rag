export interface Document {
  doc_id: string
  s3_key: string
  node_count: number
}

export interface QueryResult {
  answer: string
  used_node_ids: string[]
  raw_context_excerpt: string
}

export interface PresignResult {
  presigned_url: string
  s3_key: string
}

export interface Toast {
  id: string
  message: string
  type: 'success' | 'error' | 'info'
}

export type UploadStage =
  | 'idle'
  | 'presigning'
  | 'uploading'
  | 'indexing'
  | 'done'
  | 'error'
