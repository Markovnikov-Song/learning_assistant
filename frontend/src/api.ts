export type Subject = {
  id: string
  name: string
  description: string
  category: string
  archived: boolean
  created_at: string
  updated_at: string
}

export type DocumentItem = {
  id: string
  subject_id: string
  source_name: string
  mime_type: string
  sha256: string
  size_bytes: number
  status: 'ready' | 'processing' | 'failed'
  error: string
  created_at: string
  updated_at: string
}

export type Citation = {
  source_name: string
  page_or_section?: string
  position_hint?: string
  chunk_id: string
}

export type AskResponse = {
  answer: string
  citations: Citation[]
  found: boolean
  conversation_id?: string | null
}

export type SolveResponse = {
  found: boolean
  output_markdown: string
  citations: Citation[]
}

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.headers || {}),
    },
  })
  if (!res.ok) {
    const txt = await res.text().catch(() => '')
    throw new Error(txt || `HTTP ${res.status}`)
  }
  return (await res.json()) as T
}

export const api = {
  listSubjects: () => http<Subject[]>('/subjects'),
  createSubject: (payload: { name: string; description: string; category: string }) =>
    http<Subject>('/subjects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  patchSubject: (id: string, payload: Partial<{ name: string; description: string; category: string; archived: boolean }>) =>
    http<Subject>(`/subjects/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  deleteSubject: (id: string) => http<{ deleted: boolean }>(`/subjects/${id}`, { method: 'DELETE' }),

  listDocs: (subjectId: string) => http<DocumentItem[]>(`/subjects/${subjectId}/documents`),
  uploadDoc: async (subjectId: string, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch(`${API_BASE}/subjects/${subjectId}/documents/upload`, { method: 'POST', body: fd })
    if (!res.ok) throw new Error((await res.text().catch(() => '')) || `HTTP ${res.status}`)
    return (await res.json()) as DocumentItem
  },
  deleteDoc: (subjectId: string, docId: string) => http<{ deleted: boolean }>(`/subjects/${subjectId}/documents/${docId}`, { method: 'DELETE' }),

  ask: (subjectId: string, question: string) =>
    http<AskResponse>(`/subjects/${subjectId}/ask`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) }),
  solve: (subjectId: string, problem_text: string) =>
    http<SolveResponse>(`/subjects/${subjectId}/solve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ problem_text }) }),
}

