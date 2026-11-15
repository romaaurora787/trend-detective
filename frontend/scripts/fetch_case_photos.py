"""Fetch a NASA GIBS image per case place, outline the tested box, save as a card photo.
Usage (from backend/, which has httpx + Pillow): uv run python ../frontend/scripts/fetch_case_photos.py ../frontend/public/cases
import io, math, sys
import httpx
from PIL import Image, ImageDraw

OUT = sys.argv[1]
LAYER = sys.argv[2] if len(sys.argv) > 2 else "BlueMarble_NextGeneration"
DATE = sys.argv[3] if len(sys.argv) > 3 else None
W, H = 800, 400
R = 6378137.0
CASES = {  # lat_min, lat_max, lon_min, lon_max (same boxes as CaseView CASES)
    "lincolnshire": (52.6, 53.7, -1, 0.4),
    "england-wales": (50, 55.5, -6, 2),
    "wisconsin": (44, 46, -91, -89),
    "delhi": (28, 29.5, 76.5, 78),
    "luzon": (14, 16, 119, 121),
}
mx = lambda lon: R * math.radians(lon)
my = lambda lat: R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

def get(url):
    r = httpx.get(url, timeout=60); r.raise_for_status()
    assert r.headers["content-type"].startswith("image/"), r.text[:200]
    return Image.open(io.BytesIO(r.content)).convert("RGB")

def wms(crs, bbox, w, h):
    t = f"&TIME={DATE}" if DATE else ""
    return (f"https://gibs.earthdata.nasa.gov/wms/{crs.replace(':', '').lower()}/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0"
            f"&LAYERS={LAYER}&STYLES=&CRS={crs}&BBOX={','.join(f'{v:.1f}' for v in bbox)}&WIDTH={w}&HEIGHT={h}&FORMAT=image/jpeg{t}")

for slug, (la0, la1, lo0, lo1) in CASES.items():
    x0, x1, y0, y1 = mx(lo0), mx(lo1), my(la0), my(la1)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    # Box takes ~40% of the frame (min 700 km wide), 2:1 frame.
    ew = max((x1 - x0) / 0.4, (y1 - y0) / 0.6 * 2, 700e3 / math.cos(math.radians((la0 + la1) / 2)))
    eh = ew / 2
    bx = (cx - ew / 2, cy - eh / 2, cx + ew / 2, cy + eh / 2)
    img = get(wms("EPSG:3857", bx, W, H))
    px = lambda x: (x - bx[0]) / ew * W
    py = lambda y: (bx[3] - y) / eh * H
    d = ImageDraw.Draw(img)
    for off, col in ((2, (0, 0, 0)), (0, (255, 255, 255))):  # white line with a soft dark edge
        d.rectangle([px(x0) - off, py(y1) - off, px(x1) + off, py(y0) + off], outline=col, width=2)
    img.save(f"{OUT}/{slug}.jpg", quality=78, optimize=True, progressive=True)
    print(slug, "ok")

# World card: the whole planet, no box.
img = get(wms("EPSG:4326", (-90, -180, 90, 180), W, H))
img.save(f"{OUT}/world.jpg", quality=78, optimize=True, progressive=True)
print("world ok")
