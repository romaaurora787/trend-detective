"""'Check our work': links that let anyone redo a case outside our app.

  NASA POWER   the exact API request behind our number (CSV, no login)
  Giovanni     the same box and months in NASA GES DISC Giovanni, from the
               MERRA-2 collection POWER draws on (area-averaged time series;
               free Earthdata login). For rain we also link GPM IMERG, an
               independent satellite rainfall record, the check the challenge
               Resources point to.
  MODIS        for greenness: the Planetary Computer collection + LP DAAC page

Giovanni ids follow its {collection}_{version}_{variable} pattern; MERRA-2
cloud and sunshine are MERRA-2's own fields, not the CERES record POWER uses,
so they are labelled "a different source".

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

from urllib.parse import urlencode

GIOVANNI = "https://giovanni.gsfc.nasa.gov/giovanni/#"
POWER = "https://power.larc.nasa.gov/api/temporal/monthly/regional"

# our id -> (Giovanni data id, note)
GIO = {
    "T2M": ("M2TMNXSLV_5_12_4_T2M", "same MERRA-2 field (Kelvin in Giovanni)"),
    "TS": ("M2TMNXSLV_5_12_4_TS", "same MERRA-2 field (Kelvin)"),
    "T2MDEW": ("M2TMNXSLV_5_12_4_T2MDEW", "same MERRA-2 field (Kelvin)"),
    "QV2M": ("M2TMNXSLV_5_12_4_QV2M", "same MERRA-2 field (kg/kg, not g/kg)"),
    "PRECTOTCORR": ("M2TMNXFLX_5_12_4_PRECTOTCORR", "same MERRA-2 field (kg m⁻² s⁻¹; × 86400 = mm/day)"),
    "GWETTOP": ("M2TMNXLND_5_12_4_GWETTOP", "same MERRA-2 field"),
    "GWETROOT": ("M2TMNXLND_5_12_4_GWETROOT", "same MERRA-2 field"),
    "EVLAND": ("M2TMNXLND_5_12_4_EVLAND", "same MERRA-2 field (kg m⁻² s⁻¹)"),
    "SNODP": ("M2TMNXLND_5_12_4_SNODP", "same MERRA-2 field (metres)"),
    "AOD_55": ("M2TMNXAER_5_12_4_TOTEXTTAU", "MERRA-2 total aerosol extinction at 550 nm"),
    "WS2M": ("M2TMNXFLX_5_12_4_SPEED", "MERRA-2 surface wind speed (a related height, not exactly 2 m)"),
    "CLOUD_AMT": ("M2TMNXRAD_5_12_4_CLDTOT", "MERRA-2's own cloud: a different source from POWER's CERES record"),
    "ALLSKY_SFC_SW_DWN": ("M2TMNXRAD_5_12_4_SWGDN", "MERRA-2's own sunshine (W/m²): a different source from POWER's CERES record"),
    "ALLSKY_SFC_LW_DWN": ("M2TMNXRAD_5_12_4_LWGAB", "MERRA-2's own sky heat radiation (W/m²): a different source from POWER's CERES record"),
}
IMERG = "GPM_3IMERGM_07_precipitation"


def _giovanni(data_id: str, box, start: int, end: int) -> str:
    q = {"service": "ArAvTs", "starttime": f"{start}-01-01T00:00:00Z", "endtime": f"{end}-12-31T23:59:59Z",
         "bbox": f"{box[2]},{box[0]},{box[3]},{box[1]}", "data": data_id}
    return GIOVANNI + "&".join(f"{k}={v}" for k, v in q.items())


def links(var: str, box: list[float], start: int = 1981, end: int = 2025, power_param: str | None = None) -> list[dict]:
    out = []
    if var == "NDVI":
        out.append({"name": "MODIS NDVI on Microsoft Planetary Computer (open data, no login)",
                    "url": "https://planetarycomputer.microsoft.com/dataset/modis-13Q1-061",
                    "note": "The exact 16-day images we averaged (MOD13Q1 v6.1, 250 m)."})
        out.append({"name": "MOD13Q1 at NASA LP DAAC (get a time series with AppEEARS)",
                    "url": "https://lpdaac.usgs.gov/products/mod13q1v061/",
                    "note": "AppEEARS (free Earthdata login) extracts the same pixels for any box."})
        return out
    from .power import DERIVED, _widen
    params = DERIVED[var][0] if var in DERIVED else (power_param or var,)
    la0, la1 = _widen(box[0], box[1], 90)  # POWER's regional API needs at least 2° each way
    lo0, lo1 = _widen(box[2], box[3], 180)
    widened = (la0, la1, lo0, lo1) != tuple(box)
    for p in params:
        q = {"parameters": p, "community": "AG", "latitude-min": round(la0, 2), "latitude-max": round(la1, 2),
             "longitude-min": round(lo0, 2), "longitude-max": round(lo1, 2), "start": max(start, 1981), "end": end,
             "format": "CSV"}
        out.append({"name": f"NASA POWER API: {p}, this area (CSV, no login)", "url": f"{POWER}?{urlencode(q)}",
                    "note": "The same request our server makes. Average the grid cells whose centres fall inside your box"
                            + (f" ({box[0]}–{box[1]}° N, {box[2]}–{box[3]}° E; the request is widened to POWER's 2° minimum)" if widened else "")
                            + " to get our series."})
    if var in GIO:
        gid, note = GIO[var]
        out.append({"name": "NASA Giovanni: area-averaged time series (free Earthdata login)",
                    "url": _giovanni(gid, box, max(start, 1981), end), "note": note})
    if var == "PRECTOTCORR":
        out.append({"name": "NASA Giovanni: GPM IMERG satellite rainfall, same box (independent check, 2000 onward)",
                    "url": _giovanni(IMERG, box, max(start, 2001), end),
                    "note": "Satellite + gauge rainfall (mm/day), a separate record from MERRA-2."})
    return out
