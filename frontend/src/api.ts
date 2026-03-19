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

export type User = {
  id: string
  username: string
  is_admin: boolean
  created_at: string
}

export type TokenResponse = {
  access_token: string
  token_type: string
  user: User
}

export type ConversationHistory = {
  id: string
  user_id: string
  subject_id: string
  question_type: 'ask' | 'solve'
  question: string
  answer: string
  citations: Citation[]
  found: boolean
  created_at: string
}

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

// 获取存储的 token
function getToken(): string | null {
  return localStorage.getItem('access_token')
}

// 保存 token
function setToken(token: string): void {
  localStorage.setItem('access_token', token)
}

// 清除 token
function clearToken(): void {
  localStorage.removeItem('access_token')
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken()
  const headers: HeadersInit = {
    ...(init?.headers || {}),
  }

  // 如果有 token，添加到请求头
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  })
  if (!res.ok) {
    const txt = await res.text().catch(() => '')
    throw new Error(txt || `HTTP ${res.status}`)
  }
  return (await res.json()) as T
}

export const api = {
  // 认证相关
  login: (username: string, password: string) =>
    http<TokenResponse>('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    }),
  register: (username: string, password: string, token: string) =>
    http<TokenResponse>('/auth/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ username, password }),
    }),
  getMe: () => http<User>('/auth/me'),

  // 学科相关
  listSubjects: () => http<Subject[]>('/subjects'),
  createSubject: (payload: { name: string; description: string; category: string }) =>
    http<Subject>('/subjects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  patchSubject: (id: string, payload: Partial<{ name: string; description: string; category: string; archived: boolean }>) =>
    http<Subject>(`/subjects/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  deleteSubject: (id: string) => http<{ deleted: boolean }>(`/subjects/${id}`, { method: 'DELETE' }),

  // 文档相关
  listDocs: (subjectId: string) => http<DocumentItem[]>(`/subjects/${subjectId}/documents`),
  uploadDoc: async (subjectId: string, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    const token = getToken()
    const headers: HeadersInit = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    const res = await fetch(`${API_BASE}/subjects/${subjectId}/documents/upload`, {
      method: 'POST',
      headers,
      body: fd,
    })
    if (!res.ok) throw new Error((await res.text().catch(() => '')) || `HTTP ${res.status}`)
    return (await res.json()) as DocumentItem
  },
  deleteDoc: (subjectId: string, docId: string) => http<{ deleted: boolean }>(`/subjects/${subjectId}/documents/${docId}`, { method: 'DELETE' }),

  // 问答和解题
  ask: (subjectId: string, question: string) =>
    http<AskResponse>(`/subjects/${subjectId}/ask`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) }),
  solve: (subjectId: string, problem_text: string) =>
    http<SolveResponse>(`/subjects/${subjectId}/solve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ problem_text }) }),

  // 对话历史相关
  getHistory: (subjectId?: string) =>
    http<ConversationHistory[]>(`/history${subjectId ? `?subject_id=${subjectId}` : ''}`),
  deleteHistory: (historyId: string) =>
    http<{ deleted: boolean }>(`/history/${historyId}`, { method: 'DELETE' }),
  exportHistory: async (historyId: string) => {
    const token = getToken()
    const headers: HeadersInit = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    const res = await fetch(`${API_BASE}/history/export/${historyId}`, {
      headers,
    })
    if (!res.ok) throw new Error((await res.text().catch(() => '')) || `HTTP ${res.status}`)
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `history_${historyId}.md`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  },
}

// 导出 token 管理函数
export const auth = {
  getToken,
  setToken,
  clearToken,
  isAuthenticated: () => !!getToken(),
}