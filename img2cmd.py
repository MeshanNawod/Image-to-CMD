"""
img2cmd.py - show images and videos in Command Prompt using characters like / - | \\

Setup (once):  pip install pillow opencv-python
Examples:
  python img2cmd.py                           (asks you for a file)
  python img2cmd.py photo.jpg
  python img2cmd.py photo.jpg --mode edges    (outline using - | / \\)
  python img2cmd.py clip.mp4                  (plays the video, Ctrl+C to stop)
  python img2cmd.py clip.mp4 --color --loop
  python img2cmd.py photos_folder             (all images in a folder)
"""
import argparse
import math
import os
import shutil
import sys
import time
from PIL import Image, ImageEnhance, ImageOps

RAMP = " .-/=#@"  # darkest -> brightest
IMG_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp")
VID_EXTS = (".mp4", ".avi", ".mov", ".mkv", ".webm", ".wmv", ".flv")


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


def convert(img, o):
    """PIL image -> one string of text art. `o` holds the options."""
    img = img.convert("RGB")
    w0, h0 = img.size
    h = max(1, int(h0 / w0 * o.width * 0.5))  # characters are ~2x taller than wide
    img = img.resize((o.width, h), Image.BILINEAR)
    img = ImageEnhance.Contrast(img).enhance(o.contrast)
    img = ImageEnhance.Brightness(img).enhance(o.brightness)
    w = o.width

    gray = ImageOps.autocontrast(img.convert("L")).load()
    rgb = img.load()
    chars = o.ramp[::-1] if o.invert else o.ramp
    n = len(chars)

    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            if o.mode == "shade":
                ch = chars[min(gray[x, y] * n // 256, n - 1)]
            else:
                ch = edge_char(gray, x, y, w, h, o.threshold)
            if o.color:
                r, g, b = rgb[x, y]
                row.append(f"\x1b[38;2;{r};{g};{b}m{ch}")
            else:
                row.append(ch)
        rows.append("".join(row) + ("\x1b[0m" if o.color else ""))
    return "\n".join(rows)


def plain_text(img, o):
    old, o.color = o.color, False
    try:
        return convert(img, o)
    finally:
        o.color = old


def show_image(path, o, many):
    try:
        img = Image.open(path)
    except Exception as e:
        print(f"Could not open {path}: {e}")
        return
    if many:
        print(f"\n=== {os.path.basename(path)} ===")
    print(convert(img, o))
    if o.save:
        out = o.save
        if many:
            stem, ext = os.path.splitext(o.save)
            out = f"{stem}_{os.path.splitext(os.path.basename(path))[0]}{ext or '.txt'}"
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(plain_text(img, o))


def play_video(path, o):
    try:
        import cv2
    except ImportError:
        print("Video needs OpenCV. Run:  pip install opencv-python")
        return
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"Could not open video: {path}")
        return
    fps = o.fps or cap.get(cv2.CAP_PROP_FPS) or 24
    vw = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 16
    vh = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 9

    # keep the whole frame on screen: shrink width if it would be too tall
    rows = shutil.get_terminal_size().lines - 1
    if vh / vw * o.width * 0.5 > rows:
        o.width = max(20, int(rows / (vh / vw * 0.5)))

    out = sys.stdout
    out.write("\x1b[2J\x1b[?25l")  # clear screen, hide cursor
    try:
        while True:
            start, i = time.perf_counter(), 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                expected = start + i / fps
                i += 1
                if time.perf_counter() > expected + 1 / fps:
                    continue  # running late: skip this frame to stay in sync
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                out.write("\x1b[H" + convert(img, o) + "\n")
                out.flush()
                wait = expected - time.perf_counter()
                if wait > 0:
                    time.sleep(wait)
            if not o.loop:
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
    ap = argparse.ArgumentParser(description="Convert images and videos to text art.")
    ap.add_argument("files", nargs="*", help="image/video file(s) or folder(s)")
    ap.add_argument("--width", type=int, help="characters per line (default: window width)")
    ap.add_argument("--mode", choices=["shade", "edges"], default="shade",
                    help="shade = brightness characters, edges = outline with - | / \\")
    ap.add_argument("--ramp", default=RAMP, help='characters dark->bright, default "%s"' % RAMP)
    ap.add_argument("--color", action="store_true", help="colored output")
    ap.add_argument("--invert", action="store_true", help="swap light and dark")
    ap.add_argument("--contrast", type=float, default=1.0, help="1.0 = normal, 1.5 = stronger")
    ap.add_argument("--brightness", type=float, default=1.0, help="1.0 = normal")
    ap.add_argument("--threshold", type=float, default=120, help="edge sensitivity (lower = more lines)")
    ap.add_argument("--save", help="save plain text of an image to this file")
    ap.add_argument("--fps", type=float, help="video: play at this speed instead of the original")
    ap.add_argument("--loop", action="store_true", help="video: repeat until Ctrl+C")
    o = ap.parse_args()

    os.system("")  # lets older Windows consoles show colors

    files = find_files(o.files or [input("Drag an image or video here and press Enter: ")])
    if not files:
        print("No images or videos found.")
        return
    o.width = o.width or max(20, shutil.get_terminal_size().columns - 1)

    for f in files:
        if f.lower().endswith(VID_EXTS):
            play_video(f, o)
        else:
            show_image(f, o, many=len(files) > 1)


if __name__ == "__main__":
    main()
