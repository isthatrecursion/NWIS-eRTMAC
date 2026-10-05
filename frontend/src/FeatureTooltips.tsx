import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { PageId } from './types'

export const pageHelp: Partial<Record<PageId, string>> = {
  brief: 'Shows the active well, upcoming risk, evidence, live signals and replay controls.',
  offsets: 'Maps nearby wells and compares surface distance with downhole separation and relevance.',
  compare: 'Aligns offset histories by formation position so events can be compared across wells.',
  evidence: 'Shows which offset records support, counter or cannot resolve the historical risk.',
  rig: 'Shows one concise advisory, key live signals and a route to its supporting sources.',
  documents: 'Opens stored reports, extracted events, source pages and interval coverage.',
  review: 'Lets reviewers correct uncertain extractions and confirm the evidence used in assessments.',
  ask: 'Turns a question into read-only data queries and returns cited, verified answers.',
  validation: 'Shows synthetic benchmark results, engineering checks and external validation gaps.',
}

export const sectionHelp: Partial<Record<PageId, Record<string, string>>> = {
  brief: {
    current: 'Combines replay depth, formation, operation and channel quality into the current well context.',
    lookahead: 'Checks historical mud-loss evidence against distance ahead and fresh live corroboration.',
    population: 'Tracks an alert from activation through acknowledgement, snooze and resolution.',
    'demo-failure': 'Replays a stale-sensor case to show why incomplete live data blocks escalation.',
    'depth-strip': 'Places the bit, formations, casing and projected event windows on one depth scale.',
    secondary: 'Shows supporting indicators for other risks and makes their limited maturity visible.',
    signals: 'Lists each live channel, value, timestamp and freshness limit used by the rules.',
  },
  offsets: {
    map: 'Shows the selected well and nearby offsets on a map; the bit marker follows synthetic replay.',
    ranking: 'Calculates well separation at the target formation and compares it with surface distance.',
    method: 'Explains why an offset is relevant, penalized or blocked for this comparison.',
  },
  compare: {
    alignment: 'Projects an event into the active well using formation position and trajectory context.',
    tracks: 'Places source and target intervals side by side with event and projected depths.',
    uncertainty: 'Shows the inputs and uncertainty that widen or block an event projection.',
  },
  evidence: {
    summary: 'Summarizes the historical evidence state for the chosen risk and interval.',
    records: 'Separates supporting events, verified clean crossings and unknown records.',
    provenance: 'Shows the policy, calculations and source links behind the evidence state.',
  },
  rig: {
    'rig-current': 'Keeps the current formation, one advisory, key signals and acknowledgement in one view.',
    advisory: 'Shows the most important current alert and the historical reason behind it.',
    acknowledge: 'Records that the operator has seen an advisory; it does not control equipment.',
  },
  documents: {
    library: 'Lists ingested reports and lets you add a PDF or text report for extraction.',
    preview: 'Shows an original report page beside its extracted events and source text.',
    coverage: 'Shows which depth intervals are verified, uncertain or not documented.',
  },
  review: {
    queue: 'Prioritizes uncertain records that could change the active look-ahead.',
    'review-detail': 'Lets a reviewer accept, correct or quarantine the selected extraction.',
    policy: 'Explains how review decisions change stored evidence while retaining an audit trail.',
  },
  ask: {
    question: 'Plans a read-only query over stored wells, events, formations and evidence.',
    plan: 'Shows the intent and deterministic data operations selected for the question.',
    answer: 'Separates sourced facts, computed results and interpretation in the answer.',
    gaps: 'Lists missing evidence and limits that prevent a stronger answer.',
    sources: 'Links each grounded answer to the report passage or structured record used.',
    limits: 'Explains why unsupported numbers or insufficient source evidence cannot become an answer.',
  },
  validation: {
    blind: 'Compares frozen alerts with hidden synthetic truth and simple baselines.',
    gold: 'Measures extraction against authored reference pages; human sign-off is tracked separately.',
    assurance: 'Displays recorded engineering and safety checks with their limitations.',
    scorecard: 'Summarizes alert counts, hits, misses and lead distance from the synthetic replay.',
    baseline: 'Compares NWIS against simpler offset-selection and document-retrieval methods.',
    replay: 'Shows the alert sequence and hidden event in the held-out synthetic case.',
    failure: 'Demonstrates how stale live data blocks an otherwise eligible escalation.',
    'gold-review': 'Allows independent reviewers to check page labels and source bounding boxes.',
    'external-readiness': 'Shows which field, production and Docker validation gates remain open.',
    'usability-study': 'Times whether an evaluator can identify the active risk and its reason.',
    'validation-results': 'Shows held-out synthetic replay outcomes and baseline comparisons.',
  },
}

const titleHelp: Record<string, string> = {
  'Formation-aligned comparison': 'Normalizes each well from formation top to base to compare events and clean crossings.',
  'Manual samples': 'Accepts timestamped channel observations when a CSV replay is not being used.',
  'Facts': 'Lists statements directly supported by retrieved structured records or source passages.',
  'Computed pattern': 'Shows deterministic comparisons produced by the query tools.',
  'Interpretation': 'Explains what the grounded facts may mean without recalculating risk.',
}

type Tip = { text: string; left: number; top: number }

export default function FeatureTooltips({ page }: { page: PageId }) {
  const [tip, setTip] = useState<Tip | null>(null)
  const current = useRef<HTMLElement | null>(null)

  useEffect(() => {
    current.current?.removeAttribute('aria-describedby')
    current.current = null
    setTip(null)
  }, [page])

  useEffect(() => {
    const root = document.getElementById('main-content')
    if (!root) return
    const decorate = () => {
      root.querySelectorAll<HTMLElement>('.content-section > h2').forEach(heading => {
        const sectionId = heading.parentElement?.id || ''
        const description = sectionHelp[page]?.[sectionId] || titleHelp[heading.textContent?.trim() || '']
        if (description) {
          heading.dataset.featureHelp = description
          heading.tabIndex = 0
        }
      })
    }
    decorate()
    const observer = new MutationObserver(decorate)
    observer.observe(root, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [page])

  useEffect(() => {
    const targetFor = (node: EventTarget | null) => node instanceof Element ? node.closest<HTMLElement>('[data-feature-help]') : null
    const hide = () => {
      current.current?.removeAttribute('aria-describedby')
      current.current = null
      setTip(null)
    }
    const show = (target: HTMLElement) => {
      const text = target.dataset.featureHelp
      if (!text || current.current === target) return
      current.current?.removeAttribute('aria-describedby')
      current.current = target
      target.setAttribute('aria-describedby', 'feature-tooltip')
      const bounds = target.getBoundingClientRect()
      const width = Math.min(320, window.innerWidth - 24)
      let left = bounds.right + 12
      let top = bounds.top
      if (left + width > window.innerWidth - 12) left = bounds.left - width - 12
      if (left < 12) {
        left = Math.max(12, Math.min(bounds.left, window.innerWidth - width - 12))
        top = bounds.bottom + 8
      }
      setTip({ text, left, top: Math.max(12, Math.min(top, window.innerHeight - 100)) })
    }
    const mouseOver = (event: MouseEvent) => { const target = targetFor(event.target); if (target) show(target) }
    const mouseOut = (event: MouseEvent) => {
      const target = targetFor(event.target)
      if (target && target === current.current && !(event.relatedTarget instanceof Node && target.contains(event.relatedTarget))) hide()
    }
    const focusIn = (event: FocusEvent) => { const target = targetFor(event.target); if (target) show(target) }
    const focusOut = (event: FocusEvent) => { if (targetFor(event.target) === current.current) hide() }
    document.addEventListener('mouseover', mouseOver)
    document.addEventListener('mouseout', mouseOut)
    document.addEventListener('focusin', focusIn)
    document.addEventListener('focusout', focusOut)
    return () => {
      document.removeEventListener('mouseover', mouseOver)
      document.removeEventListener('mouseout', mouseOut)
      document.removeEventListener('focusin', focusIn)
      document.removeEventListener('focusout', focusOut)
      current.current?.removeAttribute('aria-describedby')
      current.current = null
    }
  }, [])

  return tip && createPortal(<div className="feature-tooltip" id="feature-tooltip" role="tooltip" style={{ left: tip.left, top: tip.top }}>{tip.text}</div>, document.body)
}
