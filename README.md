# img2cmd

Turn images and videos into text art for Command Prompt, using characters like `/`, `-`, `|`, `\`, `=` and `#`.

## Requirements

- Python 3
- Pillow and OpenCV (OpenCV is only needed for video)

```
pip install pillow opencv-python
```

## Setup

1. Put `img2cmd.py` in a folder, for example `C:\imgtool`.
2. Copy your photos or videos into the same folder.
3. Open Command Prompt there (in File Explorer, click the address bar, type `cmd`, press Enter).

## Quick start

```
python img2cmd.py photo.jpg
python img2cmd.py clip.mp4
```

Or run `python img2cmd.py` and drag a file into the window when it asks.

## Video

Videos play right in the window at their original speed. Press **Ctrl+C** to stop.

```
python img2cmd.py clip.mp4
python img2cmd.py clip.mp4 --mode edges --loop
python img2cmd.py clip.mp4 --color --width 80
```

- Supports `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`, `.wmv`, `.flv`.
- No sound, picture only.
- The picture is automatically sized to fit your window height.
- If it lags, use a smaller `--width`. The player skips frames to stay in sync.
- Color mode and edges mode are slower than plain shade mode.

## Modes

**shade** (default) - brightness shown with characters from dark to bright.

**edges** - draws outlines using `-` `|` `/` `\` that follow the direction of each edge:

```
python img2cmd.py photo.jpg --mode edges
```

## Options

| Option | What it does |
|---|---|
| `--mode shade/edges` | Picture style (default shade) |
| `--width 120` | Characters per line (default: your window width) |
| `--color` | Colored characters (Windows 10+ or Windows Terminal) |
| `--invert` | Swap light and dark (for light backgrounds) |
| `--contrast 1.5` | Stronger contrast (1.0 = normal) |
| `--brightness 1.2` | Brighter picture (1.0 = normal) |
| `--threshold 80` | Edge sensitivity in edges mode (lower = more lines, default 120) |
| `--ramp " -/#"` | Your own characters, dark to bright |
| `--save out.txt` | Save an image's plain text to a file |
| `--fps 15` | Video: play at this speed instead of the original |
| `--loop` | Video: repeat until Ctrl+C |

## More examples

```
python img2cmd.py photo.jpg --mode edges --threshold 80
python img2cmd.py "C:\Users\Meshan\Pictures"          (every image and video in a folder)
python img2cmd.py a.jpg b.png --save out.txt          (saves out_a.txt, out_b.txt)
```

## Tips

- Maximize the window for a bigger, clearer picture.
- If lines wrap and look broken, use a smaller `--width`.
- Photos with clear shapes and good contrast work best in edges mode.
- Names with spaces need quotes.
- Images: `.jpg`, `.png`, `.bmp`, `.gif`, `.webp`.
