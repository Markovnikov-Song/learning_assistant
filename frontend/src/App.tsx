import { useEffect, useMemo, useState } from 'react'
import 'katex/dist/katex.min.css'
import './App.css'
import { api, auth, type AskResponse, type DocumentItem, type SolveResponse, type Subject, type User } from './api'

function App() {
  // 认证状态
  const [user, setUser] = useState<User | null>(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [registerMode, setRegisterMode] = useState(false)
  const [loginUsername, setLoginUsername] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [registerUsername, setRegisterUsername] = useState('')
  const [registerPassword, setRegisterPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [authBusy, setAuthBusy] = useState(false)
  const [authErr, setAuthErr] = useState('')

  // 应用状态
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [activeSubjectId, setActiveSubjectId] = useState<string>('')
  const [docs, setDocs] = useState<DocumentItem[]>([])

  const activeSubject = useMemo(
    () => subjects.find((s) => s.id === activeSubjectId) || null,
    [subjects, activeSubjectId],
  )

  const [createName, setCreateName] = useState('')
  const [createDesc, setCreateDesc] = useState('')
  const [createCat, setCreateCat] = useState('理科')

  const [question, setQuestion] = useState('')
  const [askResp, setAskResp] = useState<AskResponse | null>(null)

  const [problem, setProblem] = useState('')
  const [solveResp, setSolveResp] = useState<SolveResponse | null>(null)

  const [busy, setBusy] = useState<string>('')
  const [err, setErr] = useState<string>('')
  const [successMsg, setSuccessMsg] = useState<string>('')

  // 拍照相关
  const [questionImage, setQuestionImage] = useState<File | null>(null)
  const [questionImagePreview, setQuestionImagePreview] = useState<string | null>(null)
  const [solveImage, setSolveImage] = useState<File | null>(null)
  const [solveImagePreview, setSolveImagePreview] = useState<string | null>(null)

  // 检查认证状态
  useEffect(() => {
    const token = auth.getToken()
    if (token) {
      fetchUserInfo()
    }
  }, [])

  async function fetchUserInfo() {
    try {
      const u = await api.getMe()
      setUser(u)
      setIsAuthenticated(true)
    } catch (e: any) {
      auth.clearToken()
      setIsAuthenticated(false)
      setUser(null)
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setAuthErr('')
    setAuthBusy(true)
    try {
      const resp = await api.login(loginUsername, loginPassword)
      auth.setToken(resp.access_token)
      setUser(resp.user)
      setIsAuthenticated(true)
      setLoginUsername('')
      setLoginPassword('')
    } catch (e: any) {
      setAuthErr(String(e?.message || e) || '登录失败')
    } finally {
      setAuthBusy(false)
    }
  }

  function handleLogout() {
    auth.clearToken()
    setIsAuthenticated(false)
    setUser(null)
    setSubjects([])
    setActiveSubjectId('')
    setDocs([])
    setAskResp(null)
    setSolveResp(null)
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault()
    setAuthErr('')

    // 验证
    if (registerUsername.length < 3) {
      setAuthErr('用户名至少需要3个字符')
      return
    }
    if (registerPassword.length < 6) {
      setAuthErr('密码至少需要6个字符')
      return
    }
    if (registerPassword !== confirmPassword) {
      setAuthErr('两次输入的密码不一致')
      return
    }

    setAuthBusy(true)
    try {
      const resp = await api.register(registerUsername, registerPassword, '')
      auth.setToken(resp.access_token)
      setUser(resp.user)
      setIsAuthenticated(true)
      setRegisterUsername('')
      setRegisterPassword('')
      setConfirmPassword('')
    } catch (e: any) {
      setAuthErr(String(e?.message || e) || '注册失败')
    } finally {
      setAuthBusy(false)
    }
  }

  // 如果未认证，显示登录界面
  if (!isAuthenticated) {
    return (
      <div className="login-page">
        <div className="login-card">
          <h1>学科专属 RAG 学习助手</h1>
          <p className="login-subtitle">{registerMode ? '注册新账户' : '请登录以继续'}</p>

          {/* 登录/注册切换 */}
          <div className="auth-switch">
            <button
              className={`auth-switch-btn ${!registerMode ? 'active' : ''}`}
              onClick={() => setRegisterMode(false)}
            >
              登录
            </button>
            <button
              className={`auth-switch-btn ${registerMode ? 'active' : ''}`}
              onClick={() => setRegisterMode(true)}
            >
              注册
            </button>
          </div>

          {registerMode ? (
            // 注册表单
            <form onSubmit={handleRegister} className="login-form">
              <div className="form-group">
                <label>用户名</label>
                <input
                  type="text"
                  value={registerUsername}
                  onChange={(e) => setRegisterUsername(e.target.value)}
                  placeholder="请输入用户名（至少3个字符）"
                  required
                  minLength={3}
                />
              </div>
              <div className="form-group">
                <label>密码</label>
                <input
                  type="password"
                  value={registerPassword}
                  onChange={(e) => setRegisterPassword(e.target.value)}
                  placeholder="请输入密码（至少6个字符）"
                  required
                  minLength={6}
                />
              </div>
              <div className="form-group">
                <label>确认密码</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="请再次输入密码"
                  required
                  minLength={6}
                />
              </div>
              {authErr && <div className="error-message">{authErr}</div>}
              <button type="submit" disabled={authBusy}>
                {authBusy ? '注册中...' : '注册'}
              </button>
            </form>
          ) : (
            // 登录表单
            <form onSubmit={handleLogin} className="login-form">
              <div className="form-group">
                <label>用户名</label>
                <input
                  type="text"
                  value={loginUsername}
                  onChange={(e) => setLoginUsername(e.target.value)}
                  placeholder="请输入用户名"
                  required
                />
              </div>
              <div className="form-group">
                <label>密码</label>
                <input
                  type="password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  placeholder="请输入密码"
                  required
                />
              </div>
              {authErr && <div className="error-message">{authErr}</div>}
              <button type="submit" disabled={authBusy}>
                {authBusy ? '登录中...' : '登录'}
              </button>
            </form>
          )}
        </div>
      </div>
    )
  }

  async function refreshSubjects(pickFirst = false) {
    const s = await api.listSubjects()
    setSubjects(s)
    if (pickFirst && s.length && !activeSubjectId) setActiveSubjectId(s[0].id)
  }

  async function refreshDocs(subjectId: string) {
    const d = await api.listDocs(subjectId)
    setDocs(d)
  }

  useEffect(() => {
    refreshSubjects(true).catch((e) => setErr(String(e?.message || e)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!activeSubjectId) return
    refreshDocs(activeSubjectId).catch((e) => setErr(String(e?.message || e)))
  }, [activeSubjectId])

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-title">学科专属 RAG 学习助手</div>
          <div className="brand-sub">严格资料内生成 · 学科隔离 · 理工科优先</div>
        </div>
        <div className="user-info">
          <span className="user-name">{user?.username} {user?.is_admin ? <span className="admin-badge">管理员</span> : null}</span>
          <button onClick={handleLogout} className="logout-btn">
            退出登录
          </button>
        </div>
        <div className="status">
          {busy ? <span className="pill busy">{busy}</span> : <span className="pill ok">就绪</span>}
          {successMsg ? <span className="pill success">{successMsg}</span> : null}
          {err ? <span className="pill err">{err}</span> : null}
        </div>
      </header>

      <main className="grid">
        <section className="card">
          <h2>① 学科</h2>
          <div className="row">
            <select value={activeSubjectId} onChange={(e) => setActiveSubjectId(e.target.value)}>
              <option value="" disabled>
                选择学科…
              </option>
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <button
              onClick={async () => {
                setErr('')
                setBusy('刷新学科…')
                try {
                  await refreshSubjects()
                } catch (e: any) {
                  setErr(String(e?.message || e))
                } finally {
                  setBusy('')
                }
              }}
            >
              刷新
            </button>
            {activeSubjectId && (
              <button
                className="danger"
                onClick={async () => {
                  if (!confirm('确定要删除当前学科吗？此操作将删除该学科下的所有资料和向量索引，且无法恢复！')) {
                    return
                  }
                  setErr('')
                  setSuccessMsg('')
                  setBusy('删除学科…')
                  try {
                    await api.deleteSubject(activeSubjectId)
                    setSuccessMsg('学科已删除')
                    setActiveSubjectId('')
                    setDocs([])
                    await refreshSubjects()
                    setTimeout(() => setSuccessMsg(''), 3000)
                  } catch (e: any) {
                    setErr(String(e?.message || e))
                  } finally {
                    setBusy('')
                  }
                }}
              >
                删除
              </button>
            )}
          </div>

          <div className="subcard">
            <div className="subcard-title">新建学科</div>
            <div className="stack">
              <input placeholder="学科名称（如：高等数学）" value={createName} onChange={(e) => setCreateName(e.target.value)} />
              <input placeholder="描述（可选）" value={createDesc} onChange={(e) => setCreateDesc(e.target.value)} />
              <div className="row">
                <select value={createCat} onChange={(e) => setCreateCat(e.target.value)}>
                  <option value="文科">文科</option>
                  <option value="理科">理科</option>
                  <option value="工科">工科</option>
                  <option value="农学">农学</option>
                  <option value="医学">医学</option>
                </select>
                <button
                  disabled={!createName.trim()}
                  onClick={async () => {
                    setErr('')
                    setSuccessMsg('')
                    setBusy('创建学科…')
                    try {
                      const s = await api.createSubject({ name: createName.trim(), description: createDesc.trim(), category: createCat })
                      setCreateName('')
                      setCreateDesc('')
                      setSuccessMsg(`学科「${s.name}」创建成功！`)
                      await refreshSubjects()
                      setActiveSubjectId(s.id)
                      setTimeout(() => setSuccessMsg(''), 3000)
                    } catch (e: any) {
                      setErr(String(e?.message || e))
                    } finally {
                      setBusy('')
                    }
                  }}
                >
                  创建
                </button>
              </div>
            </div>
          </div>
        </section>

        <section className="card">
          <h2>② 资料（当前学科：{activeSubject?.name || '未选择'}）</h2>
          <div className="row">
            <input
              type="file"
              multiple={false}
              disabled={!activeSubjectId}
              onChange={async (e) => {
                const f = e.target.files?.[0]
                if (!f || !activeSubjectId) return
                setErr('')
                setBusy('上传并解析…（大文件可能稍久）')
                try {
                  await api.uploadDoc(activeSubjectId, f)
                  await refreshDocs(activeSubjectId)
                } catch (ex: any) {
                  setErr(String(ex?.message || ex))
                } finally {
                  setBusy('')
                  e.target.value = ''
                }
              }}
            />
            <button
              disabled={!activeSubjectId}
              onClick={async () => {
                if (!activeSubjectId) return
                setErr('')
                setBusy('刷新资料…')
                try {
                  await refreshDocs(activeSubjectId)
                } catch (e: any) {
                  setErr(String(e?.message || e))
                } finally {
                  setBusy('')
                }
              }}
            >
              刷新
            </button>
          </div>

          <div className="doclist">
            {docs.length === 0 ? (
              <div className="muted">还没有资料。上传教材/PPT/笔记后再提问或解题。</div>
            ) : (
              docs.map((d) => (
                <div key={d.id} className="doc">
                  <div className="doc-main">
                    <div className="doc-title">{d.source_name}</div>
                    <div className="doc-meta">
                      <span className={`pill ${d.status === 'ready' ? 'ok' : d.status === 'failed' ? 'err' : 'busy'}`}>{d.status}</span>
                      <span className="muted">{Math.round(d.size_bytes / 1024)} KB</span>
                      {d.error ? <span className="muted errtxt">{d.error}</span> : null}
                    </div>
                  </div>
                  <button
                    className="danger"
                    onClick={async () => {
                      if (!activeSubjectId) return
                      setErr('')
                      setBusy('删除资料…')
                      try {
                        await api.deleteDoc(activeSubjectId, d.id)
                        await refreshDocs(activeSubjectId)
                      } catch (e: any) {
                        setErr(String(e?.message || e))
                      } finally {
                        setBusy('')
                      }
                    }}
                  >
                    删除
                  </button>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="card">
          <h2>③ 问答（严格资料内生成）</h2>
          <textarea
            placeholder="在当前学科内提问，例如：给出傅里叶级数的定义并说明收敛条件（必须来自你上传的资料）。"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={!activeSubjectId}
          />
          <div className="row">
            <label className="photo-button">
              <span>📷 拍照</span>
              <input
                type="file"
                accept="image/*"
                capture="camera"
                style={{ display: 'none' }}
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) {
                    setQuestionImage(file)
                    const reader = new FileReader()
                    reader.onloadend = () => {
                      setQuestionImagePreview(reader.result as string)
                    }
                    reader.readAsDataURL(file)
                  }
                }}
              />
            </label>
            <button
              disabled={!activeSubjectId || !question.trim()}
              onClick={async () => {
                if (!activeSubjectId) return
                setErr('')
                setBusy('检索并回答…')
                setAskResp(null)
                try {
                  // 如果有图片，先上传图片
                  if (questionImage) {
                    await api.uploadDoc(activeSubjectId, questionImage)
                    await refreshDocs(activeSubjectId)
                    setQuestionImage(null)
                    setQuestionImagePreview(null)
                  }
                  const r = await api.ask(activeSubjectId, question.trim())
                  setAskResp(r)
                } catch (e: any) {
                  setErr(String(e?.message || e))
                } finally {
                  setBusy('')
                }
              }}
            >
              提问
            </button>
            <button
              onClick={() => {
                setAskResp(null)
                setQuestion('')
                setQuestionImage(null)
                setQuestionImagePreview(null)
              }}
            >
              清空
            </button>
          </div>
          {questionImagePreview && (
            <div className="image-preview">
              <img src={questionImagePreview} alt="预览" />
              <button
                className="remove-image"
                onClick={() => {
                  setQuestionImage(null)
                  setQuestionImagePreview(null)
                }}
              >
                ✕
              </button>
            </div>
          )}

          {askResp ? (
            <div className="out">
              <div className="out-title">{askResp.found ? '回答' : '未找到'}</div>
              <pre className="out-pre">{askResp.answer}</pre>
              {askResp.citations?.length ? (
                <div className="cite">
                  <div className="out-title">来源</div>
                  <ul>
                    {askResp.citations.map((c) => (
                      <li key={c.chunk_id}>
                        <span className="mono">{c.source_name}</span> {c.page_or_section ? `· ${c.page_or_section}` : ''}{' '}
                        {c.position_hint ? `· ${c.position_hint}` : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}
        </section>

        <section className="card">
          <h2>解题（固定结构输出）</h2>
          <textarea
            placeholder="粘贴题目文本（图片OCR版P0先放后端扩展，下一步加）。"
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
            disabled={!activeSubjectId}
          />
          <div className="row">
            <label className="photo-button">
              <span>📷 拍照</span>
              <input
                type="file"
                accept="image/*"
                capture="camera"
                style={{ display: 'none' }}
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) {
                    setSolveImage(file)
                    const reader = new FileReader()
                    reader.onloadend = () => {
                      setSolveImagePreview(reader.result as string)
                    }
                    reader.readAsDataURL(file)
                  }
                }}
              />
            </label>
            <button
              disabled={!activeSubjectId || !problem.trim()}
              onClick={async () => {
                if (!activeSubjectId) return
                setErr('')
                setBusy('检索并解题…')
                setSolveResp(null)
                try {
                  // 如果有图片，先上传图片
                  if (solveImage) {
                    await api.uploadDoc(activeSubjectId, solveImage)
                    await refreshDocs(activeSubjectId)
                    setSolveImage(null)
                    setSolveImagePreview(null)
                  }
                  const r = await api.solve(activeSubjectId, problem.trim())
                  setSolveResp(r)
                } catch (e: any) {
                  setErr(String(e?.message || e))
                } finally {
                  setBusy('')
                }
              }}
            >
              解题
            </button>
            <button
              onClick={() => {
                setSolveResp(null)
                setProblem('')
                setSolveImage(null)
                setSolveImagePreview(null)
              }}
            >
              清空
            </button>
          </div>
          {solveImagePreview && (
            <div className="image-preview">
              <img src={solveImagePreview} alt="预览" />
              <button
                className="remove-image"
                onClick={() => {
                  setSolveImage(null)
                  setSolveImagePreview(null)
                }}
              >
                ✕
              </button>
            </div>
          )}

          {solveResp ? (
            <div className="out">
              <div className="out-title">{solveResp.found ? '解题输出' : '未找到'}</div>
              <pre className="out-pre">{solveResp.output_markdown}</pre>
              {solveResp.citations?.length ? (
                <div className="cite">
                  <div className="out-title">来源</div>
                  <ul>
                    {solveResp.citations.map((c) => (
                      <li key={c.chunk_id}>
                        <span className="mono">{c.source_name}</span> {c.page_or_section ? `· ${c.page_or_section}` : ''}{' '}
                        {c.position_hint ? `· ${c.position_hint}` : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
      </main>
    </div>
  )
}

export default App
