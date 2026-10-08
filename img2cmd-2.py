"""
img2cmd.py - images, videos and webcam as text art (/ - | \\ = # ...) in Command Prompt

Setup (once):  pip install pillow opencv-python
Examples:
  python img2cmd.py photo.jpg
  python img2cmd.py photo.jpg --mode edges --theme matrix
  python img2cmd.py clip.mp4 --theme amber --loop          (play video, Ctrl+C to stop)
  python img2cmd.py clip.mp4 --out result.mp4               (save text-art video)
  python img2cmd.py photo.jpg --out result.png              (save text-art picture)
  python img2cmd.py --webcam                                (live camera, Ctrl+C to stop)
"""
import argparse
import math
import os
import shutil
import sys
import time
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

RAMP = " .-/=#@"  # darkest -> brightest
IMG_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp")
VID_EXTS = (".mp4", ".avi", ".mov", ".mkv", ".webm", ".wmv", ".flv")
THEMES = {
    "matrix": (0, 255, 65), "amber": (255, 176, 0), "cyan": (0, 230, 255),
    "red": (255, 60, 60), "purple": (190, 100, 255), "white": (255, 255, 255),
}
DEFAULT_FG = (210, 210, 210)  # text color in saved files when no color is used


# ---------- core: image -> grid of (character, color) ----------

def edge_char(gray, x, y, w, h, threshold):
    """Pick - | / \\ from the image gradient at (x, y); space if no edge."""
    def p(i, j):
        return gray[min(max(i, 0), w - 1), min(max(j, 0), h - 1)]
    gx = (p(x+1, y-1) + 2*p(x+1, y) + p(x+1, y+1)) - (p(x-1, y-1) + 2*p(x-1, y) + p(x-1, y+1))
    gy = (p(x-1, y+1) + 2*p(x, y+1) + p(x+1, y+1)) - (p(x-1, y-1) + 2*p(x, y-1) + p(x+1, y-1))
    if math.hypot(gx, gy) < threshold:
        return " "
    a = math.degrees(math.atan2(gx, -gy)) % 180  # direction of the edge line
    if a < 22.5 or a >= 157.5:
        return "-"
    if a < 67.5:
        return "\\"
    if a < 112.5:
        return "|"
    return "/"


def build_grid(img, o):
    """PIL image -> rows of (char, rgb or None)."""
    img = img.convert("RGB")
    w0, h0 = img.size
    w = o.width
    h = max(1, int(h0 / w0 * w * 0.5))  # characters are ~2x taller than wide
    img = img.resize((w, h), Image.BILINEAR)
    img = ImageEnhance.Contrast(img).enhance(o.contrast)
    img = ImageEnhance.Brightness(img).enhance(o.brightness)

    gray = ImageOps.autocontrast(img.convert("L")).load()
    rgb = img.load()
    chars = o.ramp[::-1] if o.invert else o.ramp
    n = len(chars)
    base = THEMES.get(o.theme)

    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            if o.mode == "shade":
                ch = chars[min(gray[x, y] * n // 256, n - 1)]
            else:
                ch = edge_char(gray, x, y, w, h, o.threshold)
            if base:
                k = 1.0 if o.mode == "edges" else 0.25 + 0.75 * gray[x, y] / 255
                col = (int(base[0] * k), int(base[1] * k), int(base[2] * k))
            elif o.color:
                col = rgb[x, y]
            else:
                col = None
            row.append((ch, col))
        rows.append(row)
    return rows


def to_plain(grid):
    return "\n".join("".join(c for c, _ in row) for row in grid)


def to_ansi(grid):
    lines = []
    for row in grid:
        parts = []
        for ch, col in row:
            if col is None or ch == " ":
                parts.append(ch)
            else:
                parts.append(f"\x1b[38;2;{col[0]};{col[1]};{col[2]}m{ch}")
        lines.append("".join(parts) + "\x1b[0m")
    return "\n".join(lines)


def to_terminal(grid, o):
    return to_ansi(grid) if (o.color or o.theme) else to_plain(grid)


# ---------- saving as picture / video ----------

class Painter:
    """Draws a grid onto a black picture using a monospace font."""
    def __init__(self, size=14):
        self.font = None
        for name in ("consola.ttf", "Consolas.ttf", "cour.ttf", "DejaVuSansMono.ttf",
                     "LiberationMono-Regular.ttf", "Menlo.ttc", "Courier New.ttf"):
            try:
                self.font = ImageFont.truetype(name, size)
                break
            except OSError:
                continue
        if self.font is None:
            self.font = ImageFont.load_default()
        ascent, descent = self.font.getmetrics() if hasattr(self.font, "getmetrics") else (size, 3)
        self.cw = max(1, math.ceil(self.font.getlength("M")))
        self.chh = ascent + descent

    def draw(self, grid):
        h, w = len(grid), len(grid[0])
        W, H = (w * self.cw) // 2 * 2 + 2, (h * self.chh) // 2 * 2 + 2  # even sizes for video
        pic = Image.new("RGB", (W, H), (0, 0, 0))
        d = ImageDraw.Draw(pic)
        for y, row in enumerate(grid):
            if all(c is None for _, c in row):
                d.text((0, y * self.chh), "".join(ch for ch, _ in row), font=self.font, fill=DEFAULT_FG)
                continue
            for x, (ch, col) in enumerate(row):
                if ch != " ":
                    d.text((x * self.cw, y * self.chh), ch, font=self.font, fill=col or DEFAULT_FG)
        return pic


def numbered(path, source, many):
    if not many:
        return path
    stem, ext = os.path.splitext(path)
    return f"{stem}_{os.path.splitext(os.path.basename(source))[0]}{ext}"


def export_video(src, o):
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print(f"Could not open video: {src}")
        return
    fps = o.fps or cap.get(cv2.CAP_PROP_FPS) or 24
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    limit = int(o.seconds * fps) if o.seconds else None
    if limit and total:
        total = min(total, limit)
    out_path = o.out
    is_gif = out_path.lower().endswith(".gif")
    painter, writer, frames, i = Painter(), None, [], 0

    while True:
        ok, frame = cap.read()
        if not ok or (limit and i >= limit):
            break
        grid = build_grid(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), o)
        pic = painter.draw(grid)
        if is_gif:
            frames.append(pic.quantize(colors=64))
        else:
            if writer is None:
                writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, pic.size)
            writer.write(cv2.cvtColor(np.array(pic), cv2.COLOR_RGB2BGR))
        i += 1
        print(f"\rRendering frame {i}" + (f"/{total}" if total else ""), end="", flush=True)
    cap.release()
    print()
    if is_gif and frames:
        frames[0].save(out_path, save_all=True, append_images=frames[1:], loop=0,
                       duration=int(1000 / fps), optimize=False)
    if writer:
        writer.release()
    print(f"Saved {out_path} ({i} frames, no sound)")


# ---------- showing ----------

def show_image(path, o, many):
    try:
        img = Image.open(path)
    except Exception as e:
        print(f"Could not open {path}: {e}")
        return
    grid = build_grid(img, o)
    if many:
        print(f"\n=== {os.path.basename(path)} ===")
    print(to_terminal(grid, o))
    if o.save:
        with open(numbered(o.save, path, many), "w", encoding="utf-8") as fh:
            fh.write(to_plain(grid))
    if o.out:
        target = numbered(o.out, path, many)
        Painter().draw(grid).save(target)
        print(f"Saved {target}")


def play(src, o, live=False):
    """Play a video file, or a live camera if live=True (src is then a camera number)."""
    try:
        import cv2
    except ImportError:
        print("Video and webcam need OpenCV. Run:  pip install opencv-python")
        return
    if live and os.name == "nt":
        cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)  # faster camera start on Windows
    else:
        cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print("Could not open the camera." if live else f"Could not open video: {src}")
        return
    fps = o.fps or (15 if live else cap.get(cv2.CAP_PROP_FPS)) or 24
    vw = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 16
    vh = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 9

    # keep the whole frame on screen: shrink width if it would be too tall
    rows = shutil.get_terminal_size().lines - 1
    if vh / vw * o.width * 0.5 > rows:
        o.width = max(20, int(rows / (vh / vw * 0.5)))

    limit = int(o.seconds * fps) if o.seconds else None
    out = sys.stdout
    out.write("\x1b[2J\x1b[?25l")  # clear screen, hide cursor
    try:
        while True:
            start, i = time.perf_counter(), 0
            while True:
                ok, frame = cap.read()
                if not ok or (limit and i >= limit):
                    break
                expected = start + i / fps
                i += 1
                if not live and time.perf_counter() > expected + 1 / fps:
                    continue  # running late: skip this frame to stay in sync
                if live:
                    frame = cv2.flip(frame, 1)  # mirror, like a real mirror
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                out.write("\x1b[H" + to_terminal(build_grid(img, o), o) + "\n")
                out.flush()
                wait = expected - time.perf_counter()
                if wait > 0:
                    time.sleep(wait)
            if live or not o.loop:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    except KeyboardInterrupt:
        pass
    finally:
        out.write("\x1b[0m\x1b[?25h\n")  # restore colors and cursor
        cap.release()


def find_files(paths):
    out = []
    for p in paths:
        p = p.strip().strip('"')
        if os.path.isdir(p):
            out += [os.path.join(p, f) for f in sorted(os.listdir(p))
                    if f.lower().endswith(IMG_EXTS + VID_EXTS)]
        else:
            out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser(description="Convert images, videos and webcam to text art.")
    ap.add_argument("files", nargs="*", help="image/video file(s) or folder(s)")
    ap.add_argument("--webcam", nargs="?", type=int, const=0, metavar="N",
                    help="live camera (camera number N, default 0). Put it last or use it alone")
    ap.add_argument("--width", type=int, help="characters per line (default: window width)")
    ap.add_argument("--mode", choices=["shade", "edges"], default="shade",
                    help="shade = brightness characters, edges = outline with - | / \\")
    ap.add_argument("--theme", choices=sorted(THEMES), help="one-color look, e.g. matrix or amber")
    ap.add_argument("--color", action="store_true", help="original photo colors")
    ap.add_argument("--ramp", default=RAMP, help='characters dark->bright, default "%s"' % RAMP)
    ap.add_argument("--invert", action="store_true", help="swap light and dark")
    ap.add_argument("--contrast", type=float, default=1.0, help="1.0 = normal, 1.5 = stronger")
    ap.add_argument("--brightness", type=float, default=1.0, help="1.0 = normal")
    ap.add_argument("--threshold", type=float, default=120, help="edge sensitivity (lower = more lines)")
    ap.add_argument("--save", help="save plain text of an image to this .txt file")
    ap.add_argument("--out", help="save as picture (.png) or video (.mp4 / .gif)")
    ap.add_argument("--fps", type=float, help="video/webcam speed (default: original / 15)")
    ap.add_argument("--seconds", type=float, help="video: only the first N seconds")
    ap.add_argument("--loop", action="store_true", help="video: repeat until Ctrl+C")
    o = ap.parse_args()

    os.system("")  # lets older Windows consoles show colors

    if o.webcam is not None:
        o.width = o.width or max(20, shutil.get_terminal_size().columns - 1)
        play(o.webcam, o, live=True)
        return

    files = find_files(o.files or [input("Drag an image or video here and press Enter: ")])
    if not files:
        print("No images or videos found.")
        return
    o.width = o.width or (100 if o.out else max(20, shutil.get_terminal_size().columns - 1))

    for f in files:
        if f.lower().endswith(VID_EXTS):
            if o.out:
                o_copy = argparse.Namespace(**vars(o))
                o_copy.out = numbered(o.out, f, len(files) > 1)
                export_video(f, o_copy)
            else:
                play(f, o)
        else:
            show_image(f, o, many=len(files) > 1)


if __name__ == "__main__":
    main()
