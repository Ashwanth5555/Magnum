"""Build the two missing 3-count box renders from the one that exists.

MAG-CAR-3 and MAG-WHT-3 are the only catalogue rows without a product image, and
both are the same *format* as MAG-ALM-3: a flat presentation box with three bars
behind oval windows, one loose bar in front, garnish on the counter. Drawing them
from scratch would put two obviously synthetic tiles next to twenty-six photos, so
instead the almond box is reused as the plate and only the confection is repainted:
the carton, the shadow, the background, the lens and the framing all carry over
untouched, which is what makes the shelf read as one set.

The repaint is histogram matching, not a hue rotation and not an evenly-spaced
palette. Each bar pixel is placed by its percentile within the source bars' own
luminance distribution and given the colour that sits at the same percentile in
the target flavour, sampled off the single-bar photo that flavour already has.
Ranking pixels rather than rescaling them is what keeps the moulded nubs, the
sheen down the left of each bar and the soft occlusion inside the windows; and it
is the only version that gets white chocolate right. A linear stretch spread the
milk-chocolate range evenly across the pale palette and produced a khaki bar,
because the real white bar is heavily skewed light - its median sits at luminance
216 in a 150-234 range, not in the middle.

Colour alone is not enough for Double Caramel. Recoloured, it came out a milk
chocolate bar studded with nuts and sitting in a pile of whole almonds - which is
the almond box, and two tiles that differ by nothing a customer can name are worse
than no tile at all. So that flavour also gets the nut relief smoothed out of the
coating and a caramel drizzle laid over it, and the almonds on the counter become
toffee. White chocolate needs none of this: the flavour reads off the colour.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

SRC = 'mag-alm-3.webp'

# Where confection can be, in the source frame. Everything outside these boxes is
# carton, stick, counter or shadow and must not be touched.
REGIONS = [
    (140, 165, 252, 445),   # window 1
    (252, 165, 360, 445),   # window 2
    (360, 165, 474, 445),   # window 3
    (330, 418, 622, 592),   # the loose bar in front
    (212, 492, 348, 598),   # garnish, left of it
    (516, 498, 618, 598),   # garnish, right of it
]

# Percentile -> colour, read off the single-bar photo each flavour already has
# (mag-car-1.webp, mag-wht-1.webp) so the tone curve is the product's own rather
# than something interpolated between two guessed endpoints.
STOPS = {
    'car': [(0.01, (45, 17, 1)), (0.05, (53, 21, 3)), (0.20, (65, 29, 7)),
            (0.35, (90, 44, 15)), (0.50, (110, 58, 27)), (0.65, (114, 64, 32)),
            (0.80, (138, 87, 38)), (0.95, (177, 130, 71)), (0.99, (191, 151, 97))],
    'wht': [(0.01, (178, 148, 90)), (0.05, (188, 156, 92)), (0.20, (205, 175, 113)),
            (0.50, (238, 216, 160)), (0.80, (243, 222, 171)), (0.95, (248, 230, 186)),
            (0.99, (248, 233, 192))],
}


def bar_mask(rgb):
    """Confection only: chocolate-toned, inside a region, holes filled.

    Filling holes is what pulls the moulded nubs and the specular highlights into
    the mask - they are lighter than the test admits, but they are surrounded by
    bar, so they belong to it. The wooden stick is re-excluded afterwards because
    it is enclosed by the bar at the bottom of each window and would otherwise be
    filled in and repainted along with it.
    """
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    choc = (B < 130) & (R < 215) & (R - G > 18) & (G - B > 4)
    h, w = R.shape
    yy, xx = np.mgrid[0:h, 0:w]
    geo = np.zeros_like(choc)
    for x0, y0, x1, y1 in REGIONS:
        geo |= (xx >= x0) & (xx <= x1) & (yy >= y0) & (yy <= y1)
    m = choc & geo
    m = ndimage.binary_closing(m, np.ones((5, 5)))
    m = ndimage.binary_fill_holes(m)
    m &= geo
    m &= (B < 132)                      # the stick, back out again
    m = ndimage.binary_opening(m, np.ones((3, 3)))
    return m


def ramp(stops, n=256):
    """Colour as a function of percentile, resampled to a 256-entry lookup."""
    t = np.linspace(0, 1, n)
    xs = [p for p, _ in stops]
    return np.stack([np.interp(t, xs, [c[i] for _, c in stops]) for i in range(3)], axis=1)


# Long axis of each bar and the width of the bar around it, for laying ribbons.
# The three in the box stand upright; the loose one lies at an angle in front.
AXES = [
    (196, 190, 196, 415, 78), (306, 190, 306, 415, 78), (416, 190, 416, 415, 78),
    (372, 502, 578, 464, 96),
]


def _stroke(d, pts, radius, colour):
    """A stroke of varying width, drawn as overlapping discs.

    `ImageDraw.line` can only do one width for the whole path, and a constant
    width is exactly what made the first attempt read as piped icing: real sauce
    is thick in the middle of a run and tapers to nothing at both ends.
    """
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        t = i / (n - 1)
        r = radius * (0.30 + 0.70 * np.sin(np.pi * t) ** 0.55)
        d.ellipse([x - r, y - r, x + r, y + r], fill=colour)


def drizzle(size, mask, seed=7):
    """Caramel over the bars, clipped to the confection.

    Three passes offset by a pixel or two - a cast shadow, the body, and a narrow
    off-centre highlight - because a flat single-colour ribbon sits on the image
    like a sticker instead of lying on the bar.
    """
    rng = np.random.default_rng(seed)
    layer = Image.new('RGBA', size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x0, y0, x1, y1, bw in AXES:
        L = np.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        px, py = -uy, ux                      # unit normal, to wave across
        for k in range(2):
            phase = rng.uniform(0, 6.28)
            amp = rng.uniform(0.14, 0.20) * bw
            off = (k - 0.5) * 0.34 * bw
            pts = []
            for t in np.linspace(0.05, 0.95, 90):
                wav = amp * (np.sin(phase + t * 4.4) + 0.35 * np.sin(phase * 2 + t * 9.5))
                pts.append((x0 + ux * L * t + px * (off + wav),
                            y0 + uy * L * t + py * (off + wav)))
            r = bw * 0.075
            for dx, dy, col, rr in ((1.6, 2.2, (44, 19, 4, 130), r),
                                    (0, 0, (170, 100, 26, 250), r),
                                    (0.4, 0.7, (206, 132, 48, 235), r * 0.72),
                                    (-1.3, -1.8, (240, 186, 106, 165), r * 0.30)):
                _stroke(d, [(x + dx, y + dy) for x, y in pts], rr, col)
    layer = layer.filter(ImageFilter.GaussianBlur(1.1))
    arr = np.asarray(layer).astype(np.float32)
    arr[..., 3] *= mask                        # never outside the confection
    return arr


def recolour(src, key, out_path):
    im = Image.open(src).convert('RGB')
    rgb = np.asarray(im).astype(np.float32)
    m = bar_mask(rgb.astype(np.int16))

    if key == 'car':
        # Take the almond relief out of the coating first. Median rather than
        # blur: it flattens the chunks without softening the bar's silhouette or
        # the shading that sells its curvature.
        smooth = np.asarray(
            im.filter(ImageFilter.MedianFilter(13)).filter(ImageFilter.GaussianBlur(1.4))
        ).astype(np.float32)
        w = (ndimage.binary_erosion(m, np.ones((5, 5))).astype(np.float32) * 0.90)[..., None]
        rgb = rgb * (1 - w) + smooth * w

    lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    # Rank, don't rescale. Each pixel's percentile among the source bars becomes
    # its percentile in the target flavour, so the new bar inherits that
    # flavour's real tone curve instead of a linear ramp between two endpoints.
    src = np.sort(lum[m])
    pct = np.searchsorted(src, lum, side='left') / float(len(src))
    lut = ramp(STOPS[key])
    new = lut[np.clip((pct * 255).astype(np.int16), 0, 255)]

    # A feathered edge, or the repaint cuts a hard line against the window rim.
    alpha = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    a = (np.asarray(alpha).astype(np.float32) / 255.0)[..., None]
    outrgb = rgb * (1 - a) + new * a

    if key == 'car':
        # The garnish keeps the almonds' silhouette, so it has to stop reading as
        # nuts some other way: a deeper amber and a touch of blur turn them into
        # broken toffee sitting next to the bar.
        h_, w_ = lum.shape
        yy, xx = np.mgrid[0:h_, 0:w_]
        g = np.zeros(lum.shape, bool)
        for x0, y0, x1, y1 in REGIONS[-2:]:
            g |= (xx >= x0) & (xx <= x1) & (yy >= y0) & (yy <= y1)
        g = (g & m).astype(np.float32)
        g = np.asarray(Image.fromarray((g * 255).astype(np.uint8))
                       .filter(ImageFilter.GaussianBlur(1.6))).astype(np.float32) / 255.0
        toffee = outrgb * np.array([1.06, 0.86, 0.55])
        blur = np.asarray(Image.fromarray(np.clip(outrgb, 0, 255).astype(np.uint8))
                          .filter(ImageFilter.GaussianBlur(1.1))).astype(np.float32)
        gg = g[..., None]
        outrgb = outrgb * (1 - gg) + np.clip(0.5 * toffee + 0.5 * blur, 0, 255) * gg

        dz = drizzle(im.size, a[..., 0])
        da = (dz[..., 3] / 255.0)[..., None]
        outrgb = outrgb * (1 - da) + dz[..., :3] * da

    Image.fromarray(np.clip(outrgb, 0, 255).astype(np.uint8)).save(
        out_path, 'WEBP', quality=92, method=6)
    return int(m.sum())


if __name__ == '__main__':
    for key, name in (('car', 'mag-car-3.webp'), ('wht', 'mag-wht-3.webp')):
        n = recolour(SRC, key, name)
        print(name, 'repainted', n, 'px')
