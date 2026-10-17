import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import { BottomNav, Empty, NoteList, ProjectRail, ReminderTimeline, Section } from './components'
import { CloseIcon, PlusIcon, SearchIcon } from './icons'
import type { Dashboard, MemoryItem, Project, Tab } from './types'
import { VoiceSheet } from './VoiceSheet'

const EMPTY: Dashboard = { timezone: 'Asia/Almaty', reminders: [], projects: [], notes: [], memories: [] }

export default function App() {
  const [data, setData] = useState<Dashboard>(EMPTY)
  const [tab, setTab] = useState<Tab>('today')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [composer, setComposer] = useState('')
  const [voiceOpen, setVoiceOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState('')
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)
  const [report, setReport] = useState('')
  const [newProjectOpen, setNewProjectOpen] = useState(false)

  useEffect(() => {
    const tg = window.Telegram?.WebApp
    tg?.ready(); tg?.expand(); tg?.disableVerticalSwipes?.()
    tg?.setHeaderColor?.('#fbfcff'); tg?.setBackgroundColor?.('#fbfcff')
    api.dashboard().then(setData).catch(reason => setError(reason instanceof Error ? reason.message : 'Не удалось открыть приложение')).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!toast) return
    const timeout = window.setTimeout(() => setToast(''), 3200)
    return () => window.clearTimeout(timeout)
  }, [toast])

  useEffect(() => {
    const hasSheet = voiceOpen || Boolean(report) || newProjectOpen
    document.documentElement.classList.toggle('sheet-open', hasSheet)
    return () => document.documentElement.classList.remove('sheet-open')
  }, [voiceOpen, report, newProjectOpen])

  const processText = useCallback(async (text: string) => {
    setSaving(true)
    try {
      const result = await api.process(text)
      setData(result.dashboard)
      setToast(result.reply || 'Готово')
      setComposer('')
      window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('success')
    } catch (reason) {
      setToast(reason instanceof Error ? reason.message : 'Не удалось сохранить')
      window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('error')
      throw reason
    } finally { setSaving(false) }
  }, [])
  const transcribeVoice = useCallback(
    (blob: Blob) => api.transcribe(blob).then(result => result.transcript),
    [],
  )

  async function remove(kind: 'reminders' | 'notes' | 'memories' | 'projects', id: number) {
    try {
      const result = await api.remove(kind, id)
      if (!result.ok) throw new Error('Элемент уже удалён или недоступен')
      setData(result.dashboard)
      setToast('Удалено')
      return true
    } catch (reason) {
      setToast(reason instanceof Error ? reason.message : 'Не удалось удалить')
      window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('error')
      return false
    }
  }

  async function loadReport(project?: Project) {
    setSelectedProject(project || null)
    setReport('Готовлю отчёт…')
    try { setReport((await api.report(project?.name)).report) }
    catch { setReport('Не удалось подготовить отчёт.') }
  }

  function changeTab(next: Tab) {
    setTab(next)
    setSelectedProject(null)
    window.scrollTo({ top: 0, behavior: 'instant' })
  }

  async function createProject(name: string, description: string) {
    const result = await api.createProject(name, description)
    setData(result.dashboard)
    setNewProjectOpen(false)
    setToast('Проект создан')
  }

  if (loading) return <div className="boot"><span className="brand">WIMAX</span><i /></div>
  if (error) return <div className="fatal"><span className="brand">WIMAX</span><h1>Не удалось войти</h1><p>{error}</p><small>Откройте приложение из Telegram-бота.</small></div>

  return <div className="app-shell">
    <header><span className="brand">WIMAX</span><time>{new Date().toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}</time></header>
    <main>
      {tab === 'today' ? <TodayPage data={data} composer={composer} setComposer={setComposer} saving={saving} processText={processText} onDone={id => remove('reminders', id)} onOpenProject={project => { setSelectedProject(project); setTab('projects') }} onDeleteNote={id => remove('notes', id)} /> : null}
      {tab === 'projects' ? <ProjectsPage data={data} selected={selectedProject} setSelected={setSelectedProject} onReport={loadReport} onDelete={id => remove('projects', id).then(removed => { if (removed) setSelectedProject(null) })} onCreate={() => setNewProjectOpen(true)} onDeleteNote={id => remove('notes', id)} onDone={id => remove('reminders', id)} /> : null}
      {tab === 'database' ? <DatabasePage data={data} onDeleteNote={id => remove('notes', id)} onDone={id => remove('reminders', id)} /> : null}
      {tab === 'memory' ? <MemoryPage data={data} onDelete={id => remove('memories', id)} /> : null}
    </main>
    <BottomNav active={tab} onChange={changeTab} onVoice={() => setVoiceOpen(true)} />
    {voiceOpen ? <VoiceSheet onClose={() => setVoiceOpen(false)} onTranscribe={transcribeVoice} onSave={processText} /> : null}
    {toast ? <div className="toast" role="status">{toast}</div> : null}
    {report ? <div className="modal-layer"><button className="modal-backdrop" onClick={() => setReport('')} aria-label="Закрыть отчёт" /><article className="report-modal" role="dialog" aria-modal="true" aria-labelledby="report-title"><button className="close-button" onClick={() => setReport('')} aria-label="Закрыть отчёт"><CloseIcon /></button><small>{selectedProject?.name || 'Все проекты'}</small><h2 id="report-title">Отчёт</h2><div aria-live="polite">{report}</div></article></div> : null}
    {newProjectOpen ? <NewProjectSheet onClose={() => setNewProjectOpen(false)} onCreate={createProject} /> : null}
  </div>
}

function TodayPage({ data, composer, setComposer, saving, processText, onDone, onOpenProject, onDeleteNote }: { data: Dashboard; composer: string; setComposer: (value: string) => void; saving: boolean; processText: (value: string) => Promise<void>; onDone: (id: number) => void; onOpenProject: (project: Project) => void; onDeleteNote: (id: number) => void }) {
  return <>
    <h1>Сегодня</h1>
    <form className="quick-capture" onSubmit={event => { event.preventDefault(); if (composer.trim()) void processText(composer).catch(() => undefined) }}>
      <SearchIcon /><input value={composer} onChange={event => setComposer(event.target.value)} placeholder="Напомнить или записать мысль…" aria-label="Быстрый ввод" /><button disabled={saving || !composer.trim()} aria-label="Добавить"><PlusIcon /></button>
    </form>
    <Section title="Ближайшее"><ReminderTimeline reminders={data.reminders} onDone={onDone} timezone={data.timezone} /></Section>
    <Section title="Проекты"><ProjectRail projects={data.projects} onOpen={onOpenProject} /></Section>
    <Section title="Недавние заметки"><NoteList notes={data.notes} onDelete={onDeleteNote} /></Section>
  </>
}

function ProjectsPage({ data, selected, setSelected, onReport, onDelete, onCreate, onDeleteNote, onDone }: { data: Dashboard; selected: Project | null; setSelected: (project: Project | null) => void; onReport: (project?: Project) => void; onDelete: (id: number) => void; onCreate: () => void; onDeleteNote: (id: number) => void; onDone: (id: number) => void }) {
  const [descriptionExpanded, setDescriptionExpanded] = useState(false)
  const descriptionScroll = useRef<number | null>(null)
  useEffect(() => {
    setDescriptionExpanded(false)
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [selected?.id])

  useLayoutEffect(() => {
    if (descriptionScroll.current === null) return
    window.scrollTo({ top: descriptionScroll.current, behavior: 'instant' })
    descriptionScroll.current = null
  }, [descriptionExpanded])

  function toggleDescription() {
    descriptionScroll.current = window.scrollY
    setDescriptionExpanded(value => !value)
  }

  if (selected) {
    const notes = data.notes.filter(item => item.project_id === selected.id)
    const reminders = data.reminders.filter(item => item.project_id === selected.id)
    const longDescription = selected.description.length > 180
    return <>
      <button className="back-link" onClick={() => setSelected(null)}>‹ Все проекты</button>
      <h1 className={`project-detail-title ${selected.name.length > 32 ? 'long' : ''}`}>{selected.name}</h1>
      <p className={`page-lead project-description ${descriptionExpanded ? 'expanded' : ''}`}>{selected.description || 'Рабочее пространство проекта'}</p>
      {longDescription ? <button className="description-toggle" onClick={toggleDescription} aria-expanded={descriptionExpanded}>{descriptionExpanded ? 'Свернуть описание' : 'Показать описание полностью'}</button> : null}
      <div className="button-row"><button className="primary-compact" onClick={() => onReport(selected)}>Собрать отчёт</button><button className="danger-link" onClick={() => onDelete(selected.id)}>Удалить</button></div>
      <Section title="Напоминания"><ReminderTimeline reminders={reminders} onDone={onDone} timezone={data.timezone} /></Section>
      <Section title="Заметки"><NoteList notes={notes} onDelete={onDeleteNote} /></Section>
    </>
  }
  return <><div className="page-title-row"><div><h1>Проекты</h1><p className="page-lead">Контекст, решения и следующие шаги</p></div><button className="round-add" onClick={onCreate} aria-label="Создать проект"><PlusIcon /></button></div><div className="project-cards">{data.projects.length ? data.projects.map((project, index) => <button key={project.id} className="project-card" onClick={() => setSelected(project)}><span className={`project-mark tone-${index % 4}`}><span /></span><strong>{project.name}</strong><small>{formatCount(project.note_count, ['заметка', 'заметки', 'заметок'])} · {formatCount(project.reminder_count, ['активное', 'активных', 'активных'])}</small><ArrowBadge /></button>) : <Empty text="Назовите проект в голосовой заметке — я создам рабочее пространство сам." />}</div></>
}

function formatCount(value: number, forms: [string, string, string]) {
  const lastTwo = value % 100
  const last = value % 10
  const form = lastTwo >= 11 && lastTwo <= 14 ? forms[2] : last === 1 ? forms[0] : last >= 2 && last <= 4 ? forms[1] : forms[2]
  return `${value} ${form}`
}

function ArrowBadge() { return <span className="arrow-badge">›</span> }

function DatabasePage({ data, onDeleteNote, onDone }: { data: Dashboard; onDeleteNote: (id: number) => void; onDone: (id: number) => void }) {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<'notes' | 'reminders'>('notes')
  const normalized = query.toLocaleLowerCase('ru')
  const notes = useMemo(() => data.notes.filter(item => `${item.content} ${item.project_name || ''}`.toLocaleLowerCase('ru').includes(normalized)), [data.notes, normalized])
  const reminders = useMemo(() => data.reminders.filter(item => `${item.title} ${item.project_name || ''}`.toLocaleLowerCase('ru').includes(normalized)), [data.reminders, normalized])
  const noResults = query.trim() ? <Empty text="Ничего не найдено. Попробуйте изменить запрос." /> : null
  return <><h1>База</h1><p className="page-lead">Все записи в одном месте</p><label className="database-search"><SearchIcon /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Поиск по базе" aria-label="Поиск по базе" /></label><div className="segmented"><button className={mode === 'notes' ? 'active' : ''} onClick={() => setMode('notes')}>Заметки <span>{data.notes.length}</span></button><button className={mode === 'reminders' ? 'active' : ''} onClick={() => setMode('reminders')}>Напоминания <span>{data.reminders.length}</span></button></div>{mode === 'notes' ? (notes.length ? <NoteList notes={notes} onDelete={onDeleteNote} /> : noResults || <NoteList notes={notes} onDelete={onDeleteNote} />) : (reminders.length ? <ReminderTimeline reminders={reminders} onDone={onDone} timezone={data.timezone} /> : noResults || <ReminderTimeline reminders={reminders} onDone={onDone} timezone={data.timezone} />)}</>
}

function MemoryPage({ data, onDelete }: { data: Dashboard; onDelete: (id: number) => void }) {
  return <><h1>Память</h1><p className="page-lead">Факты, которые помогают мне понимать вас. Всё можно удалить.</p><div className="memory-list">{data.memories.length ? data.memories.map(item => <MemoryRow key={item.id} item={item} onDelete={onDelete} />) : <Empty text="Память пока пуста. Расскажите о предпочтениях, режиме и проектах." />}</div></>
}

function MemoryRow({ item, onDelete }: { item: MemoryItem; onDelete: (id: number) => void }) {
  const [expanded, setExpanded] = useState(false)
  const longValue = item.fact_value.length > 220
  return <article className="memory-row">
    <span><strong>{item.fact_key}</strong>{item.project_name ? <small>{item.project_name}</small> : null}</span>
    <p className={expanded ? 'expanded' : ''}>{item.fact_value}</p>
    {longValue ? <button className="memory-expand" onClick={() => setExpanded(value => !value)} aria-expanded={expanded}>{expanded ? 'Свернуть' : 'Показать полностью'}</button> : null}
    <button className="memory-delete" onClick={() => onDelete(item.id)}>Удалить</button>
  </article>
}

function NewProjectSheet({ onClose, onCreate }: { onClose: () => void; onCreate: (name: string, description: string) => Promise<void> }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  return <div className="modal-layer"><button className="modal-backdrop" onClick={onClose} aria-label="Закрыть" /><form className="form-sheet" onSubmit={event => { event.preventDefault(); setBusy(true); setError(''); void onCreate(name, description).catch(reason => setError(reason instanceof Error ? reason.message : 'Не удалось создать проект')).finally(() => setBusy(false)) }}><span className="sheet-handle" /><h2>Новый проект</h2><label>Название<input autoFocus maxLength={100} value={name} onChange={event => setName(event.target.value)} placeholder="Например, Orion" /></label><label>Описание<textarea maxLength={500} value={description} onChange={event => setDescription(event.target.value)} placeholder="Необязательно" /></label>{error ? <p className="form-error">{error}</p> : null}<div><button type="button" className="secondary-button" onClick={onClose}>Отмена</button><button className="primary-button" disabled={!name.trim() || busy}>Создать</button></div></form></div>
}
