import { useEffect, useState } from 'react'
import { API_BASE, request } from './api'

interface ReplayMapSnapshot {
  session: { id: string; well_id: string; adapter: string; cursor: number; frame_count: number; playing: boolean; speed: number }
  context: { bit_md_m: number | null; tvd_m: number | null; timestamp: string; channels: Record<string, {quality_status: string}> }
}

const savedRun = 'nwis-replay-run-v1'

export default function useReplayMap(wellId: string) {
  const [snapshot, setSnapshot] = useState<ReplayMapSnapshot | null>(null)
  const [status, setStatus] = useState('Connecting to replay…')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let alive = true
    let socket: WebSocket | null = null
    let poll: number | null = null
    const connect = async () => {
      let run = localStorage.getItem(savedRun)
      let initial: ReplayMapSnapshot | null = null
      if (run) {
        try { initial = await request<ReplayMapSnapshot>(`/api/replay/sessions/${encodeURIComponent(run)}`) }
        catch { localStorage.removeItem(savedRun); run = null }
      }
      if (!initial) {
        const demo = await request<{enabled: boolean; session_id: string | null}>('/api/demo/session')
        run = demo.enabled ? demo.session_id : null
        if (run) initial = await request<ReplayMapSnapshot>(`/api/replay/sessions/${encodeURIComponent(run)}`)
      }
      if (!run || !initial) {if(alive)setStatus('No active replay. Start one in Next interval brief.');return}
      if (!alive) return
      if (initial.session.well_id !== wellId) {setStatus('The active replay belongs to another well.');return}
      setSnapshot(initial)
      setStatus(initial.session.adapter === 'REPLAY' ? 'Connecting live replay stream…' : 'Manual context updates every 5 seconds')
      if (initial.session.adapter === 'REPLAY') {
        const url = new URL(API_BASE)
        url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
        socket = new WebSocket(`${url.toString().replace(/\/$/,'')}/api/v1/replay/sessions/${run}/stream`)
        socket.onopen = () => {if(alive)setStatus('Replay stream connected')}
        socket.onmessage = event => {try {const next = JSON.parse(event.data) as ReplayMapSnapshot
          if(alive && next.session.well_id === wellId)setSnapshot(next)
        } catch {if(alive)setStatus('Invalid replay update')}}
        socket.onerror = () => {if(alive)setStatus('Replay stream unavailable; controls still refresh the map')}
        socket.onclose = () => {if(alive)setStatus('Replay stream disconnected; reopen the page to reconnect')}
      } else {
        poll = window.setInterval(async () => {
          try {const next = await request<ReplayMapSnapshot>(`/api/replay/sessions/${run}`);if(alive)setSnapshot(next)}
          catch {if(alive)setStatus('Manual context unavailable')}
        }, 5000)
      }
    }
    void connect().catch(reason => {if(alive)setStatus(reason instanceof Error ? reason.message : 'Replay unavailable')})
    return () => {alive = false; socket?.close(); if(poll !== null)window.clearInterval(poll)}
  }, [wellId])

  const control = async (action: 'play' | 'pause' | 'reset') => {
    if (!snapshot || snapshot.session.adapter !== 'REPLAY' || busy) return
    setBusy(true)
    try {
      const next = await request<ReplayMapSnapshot>(`/api/replay/sessions/${snapshot.session.id}/control`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({action, speed: action === 'play' ? 20 : snapshot.session.speed}),
      })
      setSnapshot(next)
      setStatus('Replay stream connected')
    } catch (reason) {setStatus(reason instanceof Error ? reason.message : 'Replay control failed')}
    finally {setBusy(false)}
  }

  const advance = async () => {
    if (!snapshot || snapshot.session.adapter !== 'REPLAY' || busy) return
    setBusy(true)
    try {
      const next = await request<ReplayMapSnapshot>(`/api/replay/sessions/${snapshot.session.id}/advance`, {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({frames: 1}),
      })
      setSnapshot(next)
    } catch (reason) {setStatus(reason instanceof Error ? reason.message : 'Replay advance failed')}
    finally {setBusy(false)}
  }

  return {snapshot, status, busy, control, advance}
}
