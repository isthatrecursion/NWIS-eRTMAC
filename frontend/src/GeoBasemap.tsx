import { useState } from 'react'
import type { ApiOffset, ApiWell } from './api'

const WIDTH = 640
const HEIGHT = 400
const TILE = 256
const DEFAULT_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const TILE_URL = import.meta.env.VITE_MAP_TILE_URL || DEFAULT_TILE_URL

function worldPixel(latitude: number, longitude: number, zoom: number) {
  const lat = Math.max(-85.0511, Math.min(85.0511, latitude))
  const scale = TILE * 2 ** zoom
  const sin = Math.sin(lat * Math.PI / 180)
  return {
    x: (longitude + 180) / 360 * scale,
    y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * scale,
  }
}

function tileUrl(zoom: number, x: number, y: number) {
  return TILE_URL.replace('{z}', String(zoom)).replace('{x}', String(x)).replace('{y}', String(y))
}

interface MapWell { well: ApiWell; active: boolean }
interface PositionedWell extends MapWell { x: number; y: number }
interface SurveyPoint { md_m: number; x_m: number; y_m: number; tvd_m: number }

function surveyAt(points: SurveyPoint[], md: number) {
  if (!points.length || md < points[0].md_m || md > points[points.length - 1].md_m) return null
  for (let index = 0; index < points.length - 1; index++) {
    const start = points[index], end = points[index + 1]
    if (start.md_m <= md && md <= end.md_m) {
      const part = (md - start.md_m) / (end.md_m - start.md_m)
      return {md_m: md, x_m: start.x_m + part * (end.x_m - start.x_m),
        y_m: start.y_m + part * (end.y_m - start.y_m), tvd_m: start.tvd_m + part * (end.tvd_m - start.tvd_m)}
    }
  }
  return points[points.length - 1]
}

export default function GeoBasemap({active, offsets, radiusKm, selectedId, onSelect, survey, bitMd, bitQuality}: {
  active: ApiWell
  offsets: ApiOffset[]
  radiusKm: number
  selectedId: string
  onSelect: (id: string) => void
  survey?: SurveyPoint[]
  bitMd?: number | null
  bitQuality?: string
}) {
  const [tilesFailed, setTilesFailed] = useState(false)
  if (!Number.isFinite(active.latitude) || !Number.isFinite(active.longitude)) {
    return <div className="connected-map map-unavailable">This well has no geographic coordinates. Use the calculated separation table below.</div>
  }

  // The radius control also selects a suitable map scale; only visible tiles are requested.
  const zoom = radiusKm <= 1 ? 14 : radiusKm <= 3 ? 13 : 12
  const center = worldPixel(active.latitude!, active.longitude!, zoom)
  const left = center.x - WIDTH / 2
  const top = center.y - HEIGHT / 2
  const count = 2 ** zoom
  const tileRows = []
  for (let y = Math.floor(top / TILE); y <= Math.floor((top + HEIGHT) / TILE); y++) {
    if (y < 0 || y >= count) continue
    for (let x = Math.floor(left / TILE); x <= Math.floor((left + WIDTH) / TILE); x++) {
      const wrappedX = ((x % count) + count) % count
      tileRows.push({key: `${zoom}-${x}-${y}`, x: (x * TILE - left) / WIDTH * 100,
        y: (y * TILE - top) / HEIGHT * 100, url: tileUrl(zoom, wrappedX, y)})
    }
  }

  const allWells: MapWell[] = [{well: active, active: true}, ...offsets.map(row => ({well: row.well, active: false}))]
  const positioned: PositionedWell[] = allWells.filter(({well}) => Number.isFinite(well.latitude) && Number.isFinite(well.longitude))
    .map(item => {const point = worldPixel(item.well.latitude!, item.well.longitude!, zoom); return {...item, x: point.x - left, y: point.y - top}})
  const groups: PositionedWell[][] = []
  for (const item of positioned) {
    const group = groups.find(existing => Math.hypot(existing[0].x - item.x, existing[0].y - item.y) < 9)
    if (group) group.push(item)
    else groups.push([item])
  }
  const metresPerPixel = 156543.03392 * Math.cos(active.latitude! * Math.PI / 180) / 2 ** zoom
  const ringRadius = radiusKm * 1000 / metresPerPixel
  const overlapping = groups.filter(group => group.length > 1)
  const toMapPoint = (point: SurveyPoint) => {
    const latitude = active.latitude! + (point.y_m - active.y_m) / 111320
    const longitude = active.longitude! + (point.x_m - active.x_m) / (111320 * Math.cos(active.latitude! * Math.PI / 180))
    const pixel = worldPixel(latitude, longitude, zoom)
    return {x: pixel.x - left, y: pixel.y - top}
  }
  const plannedPath = survey?.map(toMapPoint) || []
  const bit = bitMd != null && bitQuality === 'FRESH' ? surveyAt(survey || [], bitMd) : null
  const bitPixel = bit ? toMapPoint(bit) : null
  const completedPath = bit && survey ? [...survey.filter(point => point.md_m < bit.md_m), bit].map(toMapPoint) : []
  const line = (points: {x:number;y:number}[]) => points.map(point => `${point.x},${point.y}`).join(' ')

  return <div className="connected-map geo-map" role="group" aria-label="Geographic context and synthetic well markers">
    <div className="geo-map-tiles" aria-hidden="true">
      {!tilesFailed && tileRows.map(tile => <img key={tile.key} src={tile.url} alt="" draggable={false}
        onError={() => setTilesFailed(true)} style={{left: `${tile.x}%`, top: `${tile.y}%`}} />)}
    </div>
    <svg className="geo-map-overlay" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} aria-hidden="true">
      <circle cx={WIDTH / 2} cy={HEIGHT / 2} r={ringRadius} fill="rgba(255,255,255,.06)" stroke="#43352b" strokeWidth="2" strokeDasharray="6 5" />
      {plannedPath.length > 1 && <polyline points={line(plannedPath)} fill="none" stroke="#215a72" strokeWidth="3" strokeDasharray="5 5" opacity=".7" />}
      {completedPath.length > 1 && <polyline points={line(completedPath)} fill="none" stroke="#126386" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />}
      <circle cx={WIDTH / 2} cy={HEIGHT / 2} r="4" fill="#111" />
    </svg>
    {bitPixel && <div className="geo-map-bit" style={{left:`${bitPixel.x/WIDTH*100}%`,top:`${bitPixel.y/HEIGHT*100}%`}}
      role="status" aria-label={`Computed bit projection at ${bit!.md_m.toFixed(1)} metres measured depth`} title={`Computed bit projection · ${bit!.md_m.toFixed(1)} m MD · ${bit!.tvd_m.toFixed(1)} m TVD`}>BIT</div>}
    {groups.map(group => {
      const first = group[0]
      const selected = group.some(item => item.well.id === selectedId)
      const label = group.length > 1 ? `${group.length} synthetic wells share this coordinate` : first.well.id
      return <button key={first.well.id} className={`geo-map-pin ${group.some(item=>item.active)?'geo-map-active':''} ${selected?'geo-map-selected':''}`}
        style={{left: `${first.x / WIDTH * 100}%`, top: `${first.y / HEIGHT * 100}%`}}
        title={label} aria-label={label} onClick={() => onSelect(group.find(item=>!item.active)?.well.id || first.well.id)}>
        {group.length > 1 ? group.length : first.active ? 'A' : '•'}
      </button>
    })}
    <div className="geo-map-note">Approximate Upper Assam context · synthetic wells · blue track = computed bit path · {radiusKm} km ring</div>
    {overlapping.length > 0 && <div className="geo-map-overlap"><strong>Shared surface point</strong>
      {overlapping.flatMap(group => group.filter(item => !item.active)).map(item => <button key={item.well.id}
        className={item.well.id === selectedId ? 'selected' : ''} onClick={() => onSelect(item.well.id)}>{item.well.id}</button>)}
    </div>}
    {tilesFailed && <div className="geo-map-fallback">Map tiles unavailable. Synthetic markers and the radius ring remain visible.</div>}
    <div className="geo-map-attribution">© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors</div>
  </div>
}
