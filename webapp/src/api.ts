import type { Dashboard } from './types'

const initData = window.Telegram?.WebApp?.initData ?? ''

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      ...options,
      headers: {
        'X-Telegram-Init-Data': initData,
        ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        ...options.headers,
      },
    })
  } catch {
    throw new Error('Нет связи. Проверьте интернет и попробуйте ещё раз.')
  }
  if (!response.ok) {
    const body = await response.text()
    let message = body
    try {
      const parsed = JSON.parse(body) as { error?: unknown }
      if (typeof parsed.error === 'string') message = parsed.error
    } catch {
      // Non-JSON errors (for example from a proxy) are already human-readable.
    }
    throw new Error(message || `Ошибка ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  dashboard: () => request<Dashboard>('/api/dashboard'),
  process: (text: string) =>
    request<{ reply: string; dashboard: Dashboard }>('/api/assistant/process', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),
  transcribe: (audio: Blob) => {
    const data = new FormData()
    data.append('audio', audio, 'voice.webm')
    return request<{ transcript: string }>('/api/voice/transcribe', {
      method: 'POST',
      body: data,
    })
  },
  remove: (kind: 'reminders' | 'notes' | 'memories' | 'projects', id: number) =>
    request<{ ok: boolean; dashboard: Dashboard }>(`/api/${kind}/${id}`, { method: 'DELETE' }),
  report: (project?: string) =>
    request<{ report: string }>('/api/report', {
      method: 'POST',
      body: JSON.stringify({ project: project || null }),
    }),
  createProject: (name: string, description: string) =>
    request<{ dashboard: Dashboard }>('/api/projects', {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    }),
}
