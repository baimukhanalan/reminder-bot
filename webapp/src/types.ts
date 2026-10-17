export type Tab = 'today' | 'projects' | 'database' | 'memory'

export interface Reminder {
  id: number
  title: string
  due_at_utc: string
  recurrence: 'none' | 'daily' | 'weekly' | 'monthly'
  reminder_kind: 'notification' | 'project_report'
  project_id: number | null
  project_name: string | null
}

export interface Project {
  id: number
  name: string
  description: string
  updated_at: string
  note_count: number
  reminder_count: number
}

export interface Note {
  id: number
  content: string
  source_type: string
  created_at: string
  project_id: number | null
  project_name: string | null
}

export interface MemoryItem {
  id: number
  fact_key: string
  fact_value: string
  confidence: number
  project_id: number | null
  project_name: string | null
  updated_at: string
}

export interface Dashboard {
  timezone: string
  reminders: Reminder[]
  projects: Project[]
  notes: Note[]
  memories: MemoryItem[]
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string
        initDataUnsafe?: { user?: { first_name?: string } }
        ready: () => void
        expand: () => void
        close: () => void
        setHeaderColor?: (color: string) => void
        setBackgroundColor?: (color: string) => void
        disableVerticalSwipes?: () => void
        HapticFeedback?: {
          impactOccurred: (style: 'light' | 'medium' | 'heavy') => void
          notificationOccurred: (type: 'error' | 'success' | 'warning') => void
        }
      }
    }
  }
}

