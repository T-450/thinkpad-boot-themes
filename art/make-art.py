import argparse
import numpy as np
from PIL import Image
from scipy import ndimage

ap = argparse.ArgumentParser()
ap.add_argument('background')
ap.add_argument('out')
ap.add_argument('--variant', choices=['a', 'b'], default='b')
ap.add_argument('--seed', type=int, default=3400)
ap.add_argument('--mask-out')
args = ap.parse_args()

rng = np.random.default_rng(args.seed)
src = np.asarray(Image.open(args.background).convert('RGB')).copy()
src[276:328, 276:890] = 40
src[1014:1052, 180:1742] = 40
base = src.astype(np.float64) / 255
H, W, _ = base.shape
canvas = base.copy()
height = np.zeros((H, W))
painted = np.zeros((H, W))

BLACK = np.array([0, 0, 0]) / 255
CHAR = np.array([18, 18, 18]) / 255
RED = np.array([0xe3, 0x27, 0x26]) / 255
IBM_R = np.array([0xd9, 0x1e, 0x27]) / 255
IBM_G = np.array([0x18, 0x81, 0x37]) / 255
IBM_B = np.array([0x01, 0x72, 0xc3]) / 255

SLOPE = (46 - 208) / 1919.0


def edge_y(x):
    return 208 + SLOPE * x


CALM = [(600, 24, 1320, 1056), (262, 22, 560, 138)]


def calm_weight():
    m = np.zeros((H, W))
    for x0, y0, x1, y1 in CALM:
        m[y0:y1, x0:x1] = 1
    d = ndimage.distance_transform_edt(1 - m)
    return np.clip(1 - d / 24.0, 0, 1)


calm = calm_weight()


def bezier(p0, p1, p2, p3, n):
    t = np.linspace(0, 1, n)[:, None]
    return ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3


def smooth_noise(n, scale):
    k = max(1, int(n / scale))
    pts = rng.normal(0, 1, k + 3)
    xs = np.linspace(0, k, n)
    return np.interp(xs, np.arange(k + 3), pts)


def stroke(pts, width, colour, opacity=0.9, bristles=None, dry=0.35, taper=(0.12, 0.3), load=1.0, relief=1.0):
    pts = np.asarray(pts, float)
    seg = np.diff(pts, axis=0)
    seglen = np.hypot(seg[:, 0], seg[:, 1])
    total = seglen.sum()
    n = max(8, int(total / 0.6))
    cum = np.concatenate([[0], np.cumsum(seglen)])
    s = np.linspace(0, total, n)
    x = np.interp(s, cum, pts[:, 0])
    y = np.interp(s, cum, pts[:, 1])
    dx = np.gradient(x)
    dy = np.gradient(y)
    norm = np.hypot(dx, dy) + 1e-9
    nx, ny = -dy / norm, dx / norm
    t = s / total
    t0, t1 = taper
    prof = np.clip(np.minimum(t / t0, (1 - t) / t1), 0, 1) ** 0.5
    wprof = width * (0.6 + 0.4 * prof) * (1 + 0.10 * smooth_noise(n, 120))
    nb = bristles or max(14, int(width * 0.8))
    offs = np.sort(rng.uniform(-0.5, 0.5, nb))
    bstr = rng.uniform(0.6, 1.0, nb)
    btone = rng.normal(1.0, 0.13, nb)
    pad = int(width) + 6
    xmin = int(max(0, x.min() - pad))
    xmax = int(min(W, x.max() + pad))
    ymin = int(max(0, y.min() - pad))
    ymax = int(min(H, y.max() + pad))
    if xmax <= xmin or ymax <= ymin:
        return
    acc = np.zeros((ymax - ymin, xmax - xmin))
    tone = np.ones_like(acc)
    paint_left = load * (1 - dry * t ** 1.3)
    edge = np.abs(offs) * 2
    for j in range(nb):
        jitter = smooth_noise(n, 50) * 0.8
        bx = x + nx * (offs[j] * wprof + jitter)
        by = y + ny * (offs[j] * wprof + jitter)
        gap = smooth_noise(n, rng.uniform(5, 26)) * (0.8 + edge[j]) + (1 - paint_left) * 2.6 - 1.0 + edge[j] * 0.6
        a = bstr[j] * prof * np.clip(1.3 - np.clip(gap, 0, None) * 1.2, 0, 1)
        xi = np.round(bx).astype(int) - xmin
        yi = np.round(by).astype(int) - ymin
        ok = (xi >= 0) & (yi >= 0) & (xi < acc.shape[1]) & (yi < acc.shape[0]) & (a > 0.02)
        np.maximum.at(acc, (yi[ok], xi[ok]), a[ok])
        tone[yi[ok], xi[ok]] = btone[j]
    acc = ndimage.grey_dilation(acc, size=(2, 3))
    tone = ndimage.grey_dilation(tone, size=(2, 3))
    acc = ndimage.gaussian_filter(acc, 0.35)
    acc = np.clip(acc * 1.2, 0, 1)
    region = (slice(ymin, ymax), slice(xmin, xmax))
    alpha = acc * opacity * (1 - calm[region])
    tint = colour + rng.normal(0, 0.01, 3)
    col = np.clip(tint[None, None, :] * tone[:, :, None] + (tone[:, :, None] - 1) * 0.05, 0, 1)
    canvas[region] = canvas[region] * (1 - alpha[:, :, None]) + col * alpha[:, :, None]
    height[region] += alpha * relief
    painted[region] = np.maximum(painted[region], alpha)


def along_edge(x0, x1, below, width, colour, jitter=6, **kw):
    xs = np.linspace(x0, x1, 4)
    ys = edge_y(xs) + below + rng.normal(0, jitter, 4)
    stroke(bezier(np.array([xs[0], ys[0]]), np.array([xs[1], ys[1]]), np.array([xs[2], ys[2]]), np.array([xs[3], ys[3]]), 60), width, colour, **kw)


def ragged_band_edge(x0, x1, count, reach, flicks=10):
    for _ in range(count):
        ln = rng.uniform(140, 440)
        a = rng.uniform(x0, max(x0 + 1, x1 - ln))
        b = min(x1, a + ln)
        w = rng.uniform(22, 58)
        below = w * rng.uniform(0.15, 0.55) + rng.uniform(0, reach)
        along_edge(a, b, below, w, BLACK, jitter=5, opacity=rng.uniform(0.8, 1.0), dry=rng.uniform(0.45, 0.85), taper=(rng.uniform(0.08, 0.3), rng.uniform(0.25, 0.55)))
    for _ in range(flicks):
        xa = rng.uniform(x0 + 20, x1 - 60)
        p0 = np.array([xa, edge_y(xa) + rng.uniform(4, 16)])
        ang = np.arctan(SLOPE) + rng.choice([-1, 1]) * rng.uniform(0.15, 0.4)
        ln = rng.uniform(60, 170)
        p3 = p0 + ln * np.array([np.cos(ang), abs(np.sin(ang)) + 0.05])
        stroke(bezier(p0, p0 + (p3 - p0) / 3, p0 + 2 * (p3 - p0) / 3, p3, 30), rng.uniform(6, 16), BLACK, opacity=rng.uniform(0.7, 0.95), dry=0.8, taper=(0.05, 0.7))


def stripes(x0, x1, y0, gap, width, colours, rise=SLOPE, **kw):
    for i, c in enumerate(colours):
        yy = y0 + i * gap
        xs = np.array([x0, x0 + (x1 - x0) / 3, x0 + 2 * (x1 - x0) / 3, x1]) + rng.normal(0, 6, 4)
        ys = yy + rise * (xs - x0) + rng.normal(0, 2.5, 4)
        stroke(bezier(*[np.array([xs[k], ys[k]]) for k in range(4)], 60), width + rng.uniform(-2, 2), c, **kw)


def sweep(p0, p3, bend, width, colour, **kw):
    p0 = np.asarray(p0, float)
    p3 = np.asarray(p3, float)
    d = p3 - p0
    nrm = np.array([-d[1], d[0]]) / (np.hypot(*d) + 1e-9)
    stroke(bezier(p0, p0 + d / 3 + nrm * bend, p0 + 2 * d / 3 + nrm * bend * 0.6, p3, 80), width, colour, **kw)


def corner(x0, x1, y0, y1, count, colours, wmin, wmax, op):
    for _ in range(count):
        a = np.array([rng.uniform(x0, x1), rng.uniform(y0, y1)])
        ln = rng.uniform(220, 460)
        ang = SLOPE + rng.uniform(-0.12, 0.12)
        b = a + ln * np.array([np.cos(np.arctan(ang)), np.sin(np.arctan(ang))])
        sweep(a, b, rng.uniform(-14, 14), rng.uniform(wmin, wmax), colours[rng.integers(len(colours))], opacity=rng.uniform(*op), dry=rng.uniform(0.4, 0.8), taper=(rng.uniform(0.05, 0.2), rng.uniform(0.25, 0.5)))


if args.variant == 'a':
    ragged_band_edge(-60, 575, 13, 30)
    ragged_band_edge(1345, 1980, 11, 26)
    corner(-260, 330, 950, 1090, 9, [CHAR, BLACK], 40, 80, (0.45, 0.85))
    corner(1420, 1700, 1020, 1100, 5, [CHAR, BLACK], 36, 70, (0.4, 0.75))
    along_edge(1372, 1912, 42, 34, RED, opacity=0.96, dry=0.5, taper=(0.04, 0.5))
    along_edge(1440, 1890, 62, 11, RED, opacity=0.8, dry=0.7, taper=(0.2, 0.5))
    stripes(1452, 1910, 948, 32, 26, [IBM_R, IBM_G, IBM_B], rise=SLOPE, opacity=0.95, dry=0.45, taper=(0.04, 0.5))
else:
    ragged_band_edge(-60, 575, 9, 18, flicks=6)
    ragged_band_edge(1345, 1980, 8, 16, flicks=6)
    stripes(-40, 568, edge_y(0) + 30, 26, 20, [IBM_R, IBM_G, IBM_B], opacity=0.95, dry=0.5, taper=(0.02, 0.4))
    stripes(1362, 1960, edge_y(1362) + 26, 26, 20, [IBM_R, IBM_G, IBM_B], opacity=0.95, dry=0.5, taper=(0.4, 0.02))
    sweep((-40, 900), (430, 1110), 60, 46, BLACK, opacity=0.85, dry=0.5)
    sweep((-40, 960), (360, 1110), 50, 34, RED, opacity=0.95, dry=0.55, taper=(0.05, 0.4))
    sweep((1960, 880), (1480, 1110), -60, 48, BLACK, opacity=0.85, dry=0.5)
    sweep((1960, 940), (1560, 1110), -50, 30, CHAR, opacity=0.8, dry=0.6)

hs = ndimage.gaussian_filter(height, 0.9)
gy, gx = np.gradient(hs)
light = -(gx * -0.6 + gy * -0.8)
relief = np.clip(1 + 2.4 * light, 0.7, 1.45)
canvas = canvas * (1 + (relief[:, :, None] - 1) * painted[:, :, None])
gr = rng.normal(0, 1, (H, W))
weave = 0.5 * np.sin(np.arange(W) * 2.1)[None, :] + 0.5 * np.sin(np.arange(H) * 1.9)[:, None]
grain = ndimage.gaussian_filter(gr, 0.6) * 0.6 + weave * 0.4
gmask = np.clip(ndimage.gaussian_filter(painted, 18) * 3, 0, 1) * (1 - calm)
canvas = canvas + grain[:, :, None] * (5.0 / 255) * gmask[:, :, None]
out = np.clip(np.round(canvas * 255), 0, 255).astype(np.uint8)
Image.fromarray(out, 'RGB').save(args.out, optimize=True)
if args.mask_out:
    Image.fromarray((np.clip(painted, 0, 1) * 255).astype(np.uint8)).save(args.mask_out)
