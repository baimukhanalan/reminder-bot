import type { ReactNode } from 'react'
import { ArrowIcon, BrainIcon, DatabaseIcon, FolderIcon, HomeIcon, MicIcon, MoreIcon, NoteIcon } from './icons'
import type { Note, Project, Reminder, Tab } from './types'

export function BottomNav({ active, onChange, onVoice }: { active: Tab; onChange: (tab: Tab) => void; onVoice: () => void }) {
  const items: Array<{ id: Tab; label: string; icon: ReactNode }> = [
    { id: 'today', label: 'Сегодня', icon: <HomeIcon /> },
    { id: 'projects', label: 'Проекты', icon: <FolderIcon /> },
    { id: 'database', label: 'База', icon: <DatabaseIcon /> },
    { id: 'memory', label: 'Память', icon: <BrainIcon /> },
  ]
  return <nav className="bottom-nav" aria-label="Основная навигация">
    {items.slice(0, 2).map(item => <NavItem key={item.id} item={item} active={active} onChange={onChange} />)}
    <button className="voice-fab" onClick={onVoice} aria-label="Голосовой ввод"><MicIcon /></button>
    {items.slice(2).map(item => <NavItem key={item.id} item={item} active={active} onChange={onChange} />)}
  </nav>
}

function NavItem({ item, active, onChange }: { item: { id: Tab; label: string; icon: ReactNode }; active: Tab; onChange: (tab: Tab) => void }) {
  return <button className={`nav-item ${active === item.id ? 'active' : ''}`} aria-current={active === item.id ? 'page' : undefined} onClick={() => onChange(item.id)}>
    {item.icon}<span>{item.label}</span>
  </button>
}

export function ReminderTimeline({ reminders, onDone, timezone }: { reminders: Reminder[]; onDone: (id: number) => void; timezone: string }) {
  if (!reminders.length) return <Empty text="На сегодня всё спокойно. Продиктуйте новое напоминание." />
  return <div className="timeline">
    {reminders.slice(0, 6).map((item, index) => {
      const date = new Date(item.due_at_utc)
      const overdue = date.getTime() < Date.now()
      const day = formatReminderDay(date, timezone)
      const meta = [day, item.project_name].filter(Boolean).join(' · ')
      return <div className="timeline-row" key={item.id}>
        <time dateTime={item.due_at_utc} className={overdue ? 'overdue' : index === 0 ? 'next' : ''}>{date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', timeZone: timezone })}</time>
        <span className={`timeline-dot ${overdue ? 'overdue' : index === 0 ? 'next' : ''}`} />
        <button className="check" onClick={() => onDone(item.id)} aria-label={`Выполнить: ${item.title}`} />
        <div className="row-main"><strong>{item.title}</strong><small>{meta}</small></div>
        <MoreIcon className="row-more" aria-hidden="true" />
      </div>
    })}
  </div>
}

function formatReminderDay(date: Date, timezone: string) {
  const dayKey = (value: Date) => new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(value)
  const today = new Date()
  if (dayKey(date) === dayKey(today)) return 'сегодня'
  const tomorrow = new Date(today.getTime() + 24 * 60 * 60 * 1000)
  if (dayKey(date) === dayKey(tomorrow)) return 'завтра'
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', timeZone: timezone })
}

export function ProjectRail({ projects, onOpen }: { projects: Project[]; onOpen: (project: Project) => void }) {
  if (!projects.length) return <Empty text="Проекты появятся сами, когда вы назовёте их в заметке." />
  return <div className="project-list">
    {projects.slice(0, 5).map((project, index) => <button className="project-row" key={project.id} onClick={() => onOpen(project)}>
      <span className={`project-mark tone-${index % 4}`}><span /></span>
      <span className="project-name">{project.name}</span>
      <span className="project-count">{project.note_count + project.reminder_count}</span>
      <ArrowIcon />
    </button>)}
  </div>
}

export function NoteList({ notes, onDelete }: { notes: Note[]; onDelete: (id: number) => void }) {
  if (!notes.length) return <Empty text="Заметок ещё нет. Нажмите плюс или скажите мысль голосом." />
  return <div className="note-list">
    {notes.slice(0, 8).map(note => <div className="note-row" key={note.id}>
      <span className="note-icon"><NoteIcon /></span>
      <div className="row-main"><strong>{note.content}</strong><small>{note.project_name || 'Без проекта'} · {new Date(note.created_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}</small></div>
      <button className="icon-button" onClick={() => onDelete(note.id)} aria-label="Удалить заметку"><MoreIcon /></button>
    </div>)}
  </div>
}

export function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return <section className="section"><div className="section-head"><h2>{title}</h2>{action}</div>{children}</section>
}

export function Empty({ text }: { text: string }) { return <p className="empty">{text}</p> }
