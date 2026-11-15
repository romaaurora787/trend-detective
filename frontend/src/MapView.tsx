import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api, examples, type Box, type MapCell, type TrendMap } from "./api";
import { useTween } from "./Chart";
import { boxText, luckText, pText, placeName, risingIsBlue, sameBox, short, signed } from "./lib";

const TILES = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}";
const ATTR = "Tiles &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors";
const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const bounds = (b: Box): L.LatLngBoundsExpression => [[b[0], b[2]], [b[1], b[3]]];

function useLeaflet(el: React.RefObject<HTMLDivElement>, box: Box, zoom?: number) {
  const map = useRef<L.Map | null>(null);
  useEffect(() => {
    if (!el.current) return;
    const m = L.map(el.current, { scrollWheelZoom: false, zoomSnap: 0.25, zoomAnimation: false });
    L.tileLayer(TILES, { attribution: ATTR, maxZoom: 10 }).addTo(m);
    if (zoom) m.setView([(box[0] + box[1]) / 2, (box[2] + box[3]) / 2], zoom, { animate: false });
    else m.fitBounds(bounds(box), { padding: [16, 16], animate: false });
    map.current = m;
    // Leaflet doesn't notice its box resizing (the flex layout settles after mount).
    const ro = new ResizeObserver(() => m.invalidateSize({ animate: false }));
    ro.observe(el.current);
    return () => { ro.disconnect(); m.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return map;
}

/** Click the map to centre a box; pick its size; use it. */
export function Picker({ box, onPick }: { box: Box; onPick: (b: Box) => void }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useLeaflet(el, box, 4);
  const [size, setSize] = useState(2);
  const [centre, setCentre] = useState<[number, number]>([(box[0] + box[1]) / 2, (box[2] + box[3]) / 2]);
  const rect = useRef<L.Rectangle | null>(null);
  const next: Box = [
    +(Math.max(centre[0] - size / 2, -90)).toFixed(2), +(Math.min(centre[0] + size / 2, 90)).toFixed(2),
    +(Math.max(centre[1] - size / 2, -180)).toFixed(2), +(Math.min(centre[1] + size / 2, 180)).toFixed(2),
  ];

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const click = (e: L.LeafletMouseEvent) => setCentre([e.latlng.lat, L.Util.wrapNum(e.latlng.lng, [-180, 180], true)]);
    m.on("click", click);
    return () => { m.off("click", click); };
  }, [map]);
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    rect.current?.remove();
    rect.current = L.rectangle(bounds(next), { color: css("--signal"), weight: 2, fillOpacity: 0.15 }).addTo(m);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [next.join()]);

  return (
    <div className="picker">
      <div ref={el} className="leaflet-host" aria-label="Map: click to choose the centre of your box" />
      <div className="picker-bar">
        <p><span className="tag">[YOUR BOX]</span> {boxText(next)}</p>
        <label>
          <span className="tag">Size</span>
          <select value={size} onChange={(e) => setSize(+e.target.value)}>
            {[0.5, 1, 2, 5, 10].map((s) => <option key={s} value={s}>{s}° × {s}°</option>)}
          </select>
        </label>
        <button className="btn" onClick={() => onPick(next)}>Use this box</button>
      </div>
    </div>
  );
}

const MAP_DEFAULT: Box = [50.0, 55.5, -6.0, 2.0];

/** The map shows the region around a place: at least 5° × 8°, so there are enough cells to compare. */
export function mapBox(b: Box): Box {
  const grow = (lo: number, hi: number, min: number, lim: number): [number, number] => {
    if (hi - lo >= min) return [lo, hi];
    const c = Math.min(Math.max((lo + hi) / 2, -lim + min / 2), lim - min / 2);
    return [+(c - min / 2).toFixed(2), +(c + min / 2).toFixed(2)];
  };
  const [a, z] = grow(b[0], b[1], 5, 90), [w, e] = grow(b[2], b[3], 8, 180);
  return [a, z, w, e];
}

/** Colour of a cell: paper at zero, full ink at the strongest slope; hue by direction. */
function cellFill(slope: number, max: number, flip: boolean) {
  const k = Math.min(Math.abs(slope) / max, 1) ** 0.8;
  const hue = (slope >= 0) !== flip ? 36 : 258;
  return `oklch(${(95 - 43 * k).toFixed(1)}% ${(0.02 + 0.17 * k).toFixed(3)} ${hue})`;
}

export default function MapView({ varId, box }: { varId: string; box: Box }) {
  const area = mapBox(box);
  const isDefault = varId === examples.map.variable.id && sameBox(area, MAP_DEFAULT);
  const [data, setData] = useState<TrendMap | null>(isDefault ? examples.map : null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<"typical" | "detective">("typical");
  const [cell, setCell] = useState<MapCell | null>(null);
  const el = useRef<HTMLDivElement>(null);
  const map = useLeaflet(el, area);
  const layer = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    setData(isDefault ? examples.map : null);
    api.map(varId, area)
      .then((d) => live && setData(d))
      .catch((e: Error) => live && setError(e.message))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [varId, area.join()]);

  const ok = data?.cells.filter((c) => c.slope_per_decade != null) ?? [];
  const max = Math.max(...ok.map((c) => Math.abs(c.slope_per_decade!)), 1e-9);
  const flip = data ? risingIsBlue(data.variable.id) : false;

  // Cells are drawn once per dataset; the Typical/Detective switch is a CSS class, so it animates.
  useEffect(() => {
    const m = map.current;
    if (!m || !data) return;
    layer.current?.remove();
    const g = L.layerGroup().addTo(m);
    const ink = css("--ink");
    const lat = data.cells.length > 1 ? Math.min(...data.cells.map((a) => Math.abs(a.lat - data.cells[0].lat)).filter((d) => d > 1e-6), 0.5) : 0.5;
    const lon = data.cells.length > 1 ? Math.min(...data.cells.map((a) => Math.abs(a.lon - data.cells[0].lon)).filter((d) => d > 1e-6), 0.625) : 0.625;
    data.cells.forEach((c, i) => {
      if (c.slope_per_decade == null) return;
      L.rectangle([[c.lat - lat / 2, c.lon - lon / 2], [c.lat + lat / 2, c.lon + lon / 2]], {
        className: `cell${c.significant_typical ? " st" : ""}${c.significant_fdr ? " sf" : ""}`,
        color: ink, weight: 1.5, fillColor: cellFill(c.slope_per_decade, max, flip), fillOpacity: 1,
      }).on("mouseover click", () => setCell(c)).addTo(g).getElement()?.setAttribute("style", `--i:${i % 40}`);
    });
    L.rectangle(bounds(box), { className: "place-box", color: ink, weight: 2, fill: false, dashArray: "6 5", interactive: false }).addTo(g);
    m.fitBounds(L.latLngBounds(data.cells.map((c) => [c.lat, c.lon] as [number, number])).pad(0.06), { animate: false });
    layer.current = g;
    setCell(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, map]);

  const s = data?.summary;
  const n = useTween(s ? (mode === "typical" ? s.n_significant_typical : s.n_significant_fdr) : 0, 800);
  const u = data ? short(data.variable.units) : "";

  return (
    <main className="sheet mapv" aria-busy={loading}>
      <section className="frame hero hero-sm">
        <div className="bar-top">
          <span className="tag">[MAP] {data?.variable.name ?? "Trend"} · around {placeName(box)}</span>
          <span className="tag" role="status">{error ? <span className="error">{error}</span> : loading ? "[LIVE] testing every NASA grid cell in this area…" : `[${s?.n_cells ?? 0} cells] each about 50 km, tested on its own`}</span>
        </div>
        <h1 className="hero-line">
          {s ? <>{s.n_significant_typical} cells look like change. <span className="hl">{s.n_significant_fdr} survive.</span></> : <>Testing every cell <span className="hl">one by one…</span></>}
        </h1>
      </section>

      <section className={`frame map-sheet mode-${mode}`}>
        <div className="map-host-wrap">
          <div ref={el} className="leaflet-host tall" aria-label="Trend map" />
          <div className="ramp" aria-label="Colour key">
            <span className="tag">{flip ? "drier" : "falling"} {signed(-max)}</span>
            <i className={flip ? "flip" : undefined} />
            <span className="tag">{signed(max)} {flip ? "wetter" : "rising"}</span>
            <span className="tag ramp-u">{u} per decade · outlined = counted as real · dashed = {placeName(box)}</span>
          </div>
        </div>
        <aside className="map-side">
          <div className="seg" role="radiogroup" aria-label="Which analysis">
            <button role="radio" aria-checked={mode === "typical"} onClick={() => setMode("typical")}>Typical analysis</button>
            <button role="radio" aria-checked={mode === "detective"} onClick={() => setMode("detective")}>The Detective</button>
          </div>
          {s && (
            <>
              <p className="map-n"><b>{Math.round(n)}</b><small>/{s.n_cells}</small></p>
              <p className="tag">{mode === "typical" ? "cells a typical analysis calls real" : "cells with proven change after correction"}</p>
              <p className="big-line">{s.story}</p>
              <ol className="ladder">
                <li className={mode === "typical" ? "on" : undefined}><b>{s.n_significant_typical}</b><span>Typical: a straight-line test that treats every month as independent.</span></li>
                <li><b>{s.n_significant_raw}</b><span>Corrected tests, one cell at a time. About {Math.round(s.n_cells * 0.05)} would pass by chance alone.</span></li>
                <li className={mode === "detective" ? "on" : undefined}><b>{s.n_significant_fdr}</b><span>After the false-discovery correction ({s.n_rising_fdr} rising, {s.n_falling_fdr} falling; Benjamini-Hochberg, q = {s.fdr_q}).</span></li>
              </ol>
              {data?.shuffled_control?.headline && <p className="control"><span className="tag">[CONTROL]</span> {data.shuffled_control.headline}</p>}
              <div className="inspect" aria-live="polite">
                <p className="tag">[CELL] {cell ? `${cell.lat.toFixed(2)}°, ${cell.lon.toFixed(2)}°` : "hover or tap a square"}</p>
                {cell && (
                  <dl className="stats">
                    <div><dt>Trend</dt><dd><b>{signed(cell.slope_per_decade)}</b> {u} per decade</dd></div>
                    <div className="tech"><dt>Corrected test</dt><dd>{pText(cell.p)}</dd></div>
                    <div className="plain-only"><dt>Luck alone</dt><dd>{luckText(cell.p)}</dd></div>
                    <div><dt>Typical says</dt><dd>{cell.significant_typical ? "real change" : "no trend"}</dd></div>
                    <div><dt>Detective says</dt><dd>{cell.significant_fdr ? "proven change" : "not proven"}</dd></div>
                  </dl>
                )}
              </div>
            </>
          )}
          {!isDefault && <a className="btn ghost" href="#/map?var=GWETROOT&box=50,55.5,-6,2">See the false-alarm lesson: England soil wetness</a>}
        </aside>
      </section>
    </main>
  );
}
