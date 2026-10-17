import { useEffect, useRef, useState } from 'react'
import { MicIcon } from './icons'

type Stage = 'requesting' | 'recording' | 'transcribing' | 'review' | 'saving'
type SpeechRecognizer = {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((event: { results: ArrayLike<{ 0: { transcript: string }; isFinal: boolean }> }) => void) | null
  start: () => void
  stop: () => void
}

export function VoiceSheet({ onClose, onTranscribe, onSave }: {
  onClose: () => void
  onTranscribe: (audio: Blob) => Promise<string>
  onSave: (text: string) => Promise<void>
}) {
  const [stage, setStage] = useState<Stage>('requesting')
  const [transcript, setTranscript] = useState('')
  const [error, setError] = useState('')
  const recorder = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])
  const stream = useRef<MediaStream | null>(null)
  const liveRecognition = useRef<SpeechRecognizer | null>(null)

  useEffect(() => {
    let active = true
    navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
      .then(media => {
        if (!active) { media.getTracks().forEach(track => track.stop()); return }
        stream.current = media
        const nextRecorder = new MediaRecorder(media)
        recorder.current = nextRecorder
        nextRecorder.ondataavailable = event => { if (event.data.size) chunks.current.push(event.data) }
        nextRecorder.onstop = async () => {
          if (!active) return
          setStage('transcribing')
          try {
            const text = await onTranscribe(new Blob(chunks.current, { type: nextRecorder.mimeType || 'audio/webm' }))
            setTranscript(text)
            setStage('review')
            window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('success')
          } catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Не удалось распознать аудио')
            setStage('review')
          }
        }
        nextRecorder.start()
        const speechWindow = window as unknown as {
          SpeechRecognition?: new () => SpeechRecognizer
          webkitSpeechRecognition?: new () => SpeechRecognizer
        }
        const Recognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition
        if (Recognition) {
          const recognition = new Recognition()
          recognition.continuous = true
          recognition.interimResults = true
          recognition.lang = 'ru-RU'
          recognition.onresult = event => {
            let draft = ''
            for (let index = 0; index < event.results.length; index += 1) {
              draft += `${event.results[index][0].transcript} `
            }
            if (draft.trim()) setTranscript(draft.trim())
          }
          try { recognition.start(); liveRecognition.current = recognition } catch { /* final transcription remains available */ }
        }
        setStage('recording')
      })
      .catch(() => { setError('Разрешите доступ к микрофону'); setStage('review') })
    return () => {
      active = false
      if (recorder.current?.state === 'recording') recorder.current.stop()
      try { liveRecognition.current?.stop() } catch { /* already stopped */ }
      stream.current?.getTracks().forEach(track => track.stop())
    }
  }, [onTranscribe])

  function finishRecording() {
    if (recorder.current?.state === 'recording') {
      recorder.current.stop()
      try { liveRecognition.current?.stop() } catch { /* already stopped */ }
      stream.current?.getTracks().forEach(track => track.stop())
    }
  }

  async function save() {
    if (!transcript.trim()) return
    setStage('saving')
    try { await onSave(transcript); onClose() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось сохранить'); setStage('review') }
  }

  const busy = stage === 'requesting' || stage === 'transcribing' || stage === 'saving'
  const heading = stage === 'requesting'
    ? 'Включаю микрофон'
    : stage === 'recording'
      ? 'Говорите, я слушаю'
      : stage === 'transcribing'
        ? 'Разбираю вашу мысль'
        : stage === 'saving'
          ? 'Сохраняю'
          : 'Проверьте текст'
  return <div className="voice-layer" role="dialog" aria-modal="true" aria-label="Голосовой ввод">
    <button className="voice-backdrop" onClick={onClose} aria-label="Закрыть" />
    <div className="voice-sheet">
      <span className="sheet-handle" />
      <h2 aria-live="polite">{heading}</h2>
      <div className={`wave ${stage === 'recording' ? 'active' : ''}`} aria-hidden="true">
        {Array.from({ length: 19 }, (_, index) => <i key={index} style={{ '--i': index, height: `${13 + (index % 5) * 7}px` } as React.CSSProperties} />)}
      </div>
      {stage === 'review' && transcript ? <textarea
        className="transcript transcript-editor"
        aria-label="Текст голосовой заметки"
        value={transcript}
        onChange={event => { setTranscript(event.target.value); setError('') }}
      /> : <div className={`transcript ${error ? 'error' : ''}`}>
        {error || transcript || (stage === 'recording' ? 'Говорите — здесь появится черновик' : busy ? '…' : 'Запись пока пустая')}
      </div>}
      {error && transcript ? <p className="voice-error" role="alert">{error}</p> : null}
      <p className="language-note">Распознаю русский, қазақша и English</p>
      <div className="voice-actions">
        <button className="secondary-button" onClick={onClose}>Отмена</button>
        <span className={`voice-orb ${stage === 'recording' ? 'recording' : ''}`}><MicIcon /></span>
        {stage === 'recording' ? <button className="primary-button" onClick={finishRecording}>Готово</button> : <button className="primary-button" onClick={save} disabled={busy || !transcript}>Создать</button>}
      </div>
    </div>
  </div>
}
