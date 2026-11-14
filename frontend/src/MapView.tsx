import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api, examples, type Box, type TrendMap } from "./api";
import { boxText, placeName, risingIsBlue, sameBox, signed } from "./lib";

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
    return () => { m.remove(); map.current = null; };
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
    rect.current = L.rectangle(bounds(next), { color: css("--rise"), weight: 2, fillOpacity: 0.12 }).addTo(m);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [next.join()]);

  return (
    <div className="picker">
      <div ref={el} className="leaflet-host" aria-label="Map: click to choose the centre of your box" />
      <div className="picker-bar">
        <p>Click anywhere on the map. Your box: <strong>{boxText(next)}</strong></p>
        <label>
          <span>Size</span>
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

export default function MapView({ varId, box }: { varId: string; box: Box }) {
  const isDefault = varId === examples.map.variable.id && sameBox(box, MAP_DEFAULT);
  const [data, setData] = useState<TrendMap | null>(isDefault ? examples.map : null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<"typical" | "detective">("typical");
  const el = useRef<HTMLDivElement>(null);
  const map = useLeaflet(el, box);
  const layer = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    api.map(varId, box)
      .then((d) => live && setData(d))
      .catch((e: Error) => live && setError(e.message))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [varId, box.join()]);

  useEffect(() => {
    const m = map.current;
    if (!m || !data) return;
    layer.current?.remove();
    const g = L.layerGroup().addTo(m);
    const slopes = data.cells.map((c) => Math.abs(c.slope_per_decade ?? 0));
    const max = Math.max(...slopes) || 1;
    const flip = risingIsBlue(data.variable.id);
    const [rise, fall, ink] = [css("--rise"), css("--fall"), css("--ink")];
    for (const c of data.cells) {
      if (c.slope_per_decade == null) continue;
      const sig = mode === "typical" ? c.significant_typical : c.significant_fdr;
      const up = c.slope_per_decade >= 0;
      const strength = Math.abs(c.slope_per_decade) / max;
      L.rectangle([[c.lat - 0.25, c.lon - 0.3125], [c.lat + 0.25, c.lon + 0.3125]], {
        stroke: sig, color: ink, weight: sig ? 1.5 : 0,
        fillColor: up !== flip ? rise : fall,
        fillOpacity: sig ? 0.25 + 0.55 * strength : 0.06 + 0.1 * strength,
      }).bindTooltip(`${signed(c.slope_per_decade)} ${data.variable.units} per decade${sig ? (mode === "typical" ? " · typical analysis calls this real" : " · survives the correction") : ""}`).addTo(g);
    }
    m.fitBounds(L.latLngBounds(data.cells.map((c) => [c.lat, c.lon] as [number, number])).pad(0.08), { animate: false });
    layer.current = g;
  }, [data, mode, map]);

  const s = data?.summary;
  const n = mode === "typical" ? s?.n_significant_typical : s?.n_significant_fdr;
  const flip = data ? risingIsBlue(data.variable.id) : false;
  return (
    <main className="page mapv" aria-busy={loading}>
      <header className="fig-head">
        <h1><span className="fig-no">Fig. 2</span> {data?.variable.name ?? "Trend"} map, {placeName(box)}</h1>
        <p className="status" role="status">
          {error ? <span className="error">{error}</span> : loading ? "Testing every NASA grid cell in this area…" : "Each square is one NASA grid cell (about 50 km), tested on its own. Boxes under 2° are widened to 2°."}
        </p>
      </header>
      <div className="plate">
        <div className="map-host-wrap">
          <div ref={el} className="leaflet-host tall" aria-label="Trend map" />
        </div>
        <aside className="legend">
          <div className="seg" role="radiogroup" aria-label="Which analysis">
            <button role="radio" aria-checked={mode === "typical"} onClick={() => setMode("typical")}>Typical analysis</button>
            <button role="radio" aria-checked={mode === "detective"} onClick={() => setMode("detective")}>The Detective</button>
          </div>
          {s && (
            <>
              <p className="bignum"><strong className="n">{n}</strong> of {s.n_cells} cells {mode === "typical" ? "look like real change" : "show proven change"}</p>
              <p className="headline">{s.story}</p>
              <dl className="facts">
                <div><dt>Typical analysis</dt><dd>{s.n_significant_typical} cells: a straight-line test that treats every month as independent</dd></div>
                <div><dt>Corrected tests, one cell at a time</dt><dd>{s.n_significant_raw} cells: about {Math.round(s.n_cells * 0.05)} would pass by chance alone</dd></div>
                <div><dt>After the false-discovery correction</dt><dd>{s.n_significant_fdr} cells ({s.n_rising_fdr} rising, {s.n_falling_fdr} falling), Benjamini-Hochberg at q = {s.fdr_q}</dd></div>
              </dl>
              {data?.shuffled_control?.headline && <p className="control">{data.shuffled_control.headline}</p>}
              <div className="key" aria-label="Colour key">
                <span><i className="sw sw-fall" />{flip ? "wetter" : "falling"}</span>
                <span><i className="sw sw-rise" />{flip ? "drier" : "rising"}</span>
                <span><i className="sw sw-sig" />outlined: counted as real in this view</span>
              </div>
            </>
          )}
          {!isDefault && <a className="btn ghost" href="#/map?var=GWETROOT&box=50,55.5,-6,2">See the false-alarm lesson: England soil wetness</a>}
        </aside>
      </div>
    </main>
  );
}
