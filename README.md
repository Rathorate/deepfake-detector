# Deepfake Video-Call Artifact Detector (Prototype)

A heuristic, artifact-based tool for flagging possible signs of deepfake /
face-swap manipulation in a video call recording or live webcam feed. Built
for internal security research and employee-awareness demonstrations.

## What it does

Analyzes each frame of a video for four classes of known deepfake artifacts:

1. **Blink irregularity** — abnormally low or erratic blink rate (some
   face-swap models are trained on datasets with few closed-eye frames).
2. **Face-boundary blending** — irregular edge gradients right at the
   face/background seam, which can indicate a composited mask.
3. **Temporal flicker** — frame-to-frame instability in the face region.
4. **Position/size jitter** — more frame-to-frame face movement than
   expected for natural motion, which can indicate unstable synthesis.

It aggregates these into a `low` / `medium` / `high` suspicion level with
a human-readable explanation of which signals fired.

## What it is NOT

- **Not a trained classifier.** It uses classical computer vision (OpenCV
  Haar cascades + gradient/frame-difference analysis), not a neural network
  trained on labeled real/fake video pairs.
- **Not validated against a labeled dataset.** The thresholds are
  reasonable starting points, not calibrated. Before you trust its output,
  run it against known-real and known-fake clips (e.g. from FaceForensics++,
  DFDC, or Celeb-DF) and tune the thresholds in `detector.py` accordingly.
- **Not a substitute for a real security control.** It will miss
  high-quality modern deepfakes and will false-positive on ordinary poor
  video quality (bad lighting, low bitrate, webcam noise). Use it as one
  input to a broader verification process (e.g. out-of-band confirmation
  for sensitive requests), not as a pass/fail gate.

## Install

```bash
pip install -r requirements.txt
```

No model files need to be downloaded — the detector uses cascade
classifiers that ship with `opencv-python`.

### Known issue: opencv-python 5.0.0.93

At the time of writing, `opencv-python==5.0.0.93` ships without a working
`cv2.CascadeClassifier`, which this tool depends on. `requirements.txt` is
pinned to `opencv-python==4.10.0.84`, a version confirmed to work. If you
hit `AttributeError: module 'cv2' has no attribute 'CascadeClassifier'`,
confirm your installed version and re-pin:

```bash
pip list | grep opencv
pip uninstall opencv-python opencv-python-headless opencv-contrib-python -y
pip install opencv-python==4.10.0.84
python3 -c "import cv2; print(cv2.__version__); print(hasattr(cv2, 'CascadeClassifier'))"
```

The last line should print `True`.

## Usage

Analyze a recorded video file:

```bash
python3 detector.py --input path/to/call_recording.mp4 --report report.json
```

Analyze a live webcam feed (press `q` to stop and see the report):

```bash
python3 detector.py --webcam
```

Optional flags:

```bash
python3 detector.py --webcam --camera-index 1 --seconds 30 --report report.json
python3 detector.py --input video.mp4 --show   # preview window while analyzing a file
```

**Note on WSL:** WSL does not pass through webcam devices by default, so
`--webcam` will fail with a "could not open webcam" error unless you've
set up USB/camera passthrough (e.g. via `usbipd-win`). File-based
analysis (`--input`) works normally on WSL with no extra setup.

## Output

A JSON report with per-metric statistics, an overall suspicion level, and
plain-language flags explaining what was detected, e.g.:

```json
{
  "suspicion_level": "medium",
  "suspicion_points": 1,
  "suspicion_points_max": 4,
  "flags": [
    "Face-boundary blending looks unusually smooth/uniform ..."
  ]
}
```

### How to read the suspicion level

Don't treat `suspicion_level` as a verdict — treat `suspicion_points` as
the more informative number. In testing, a single flag firing (1/4),
especially the boundary-blend signal on a compressed or screen-recorded
video, is consistent with normal compression artifacts rather than
manipulation — that signal is the most prone to false positives. Multiple
flags firing together (2+/4), especially blink rate combined with either
flicker or jitter, is a stronger signal worth taking seriously. Always
weigh this against the disclaimer below.

## Suggested next steps for a real security initiative

- Validate against labeled datasets and tune thresholds before any
  operational use. The boundary-blend threshold (`< 15` in
  `summarize()`) is a good first candidate to loosen if you see it firing
  on known-real, well-lit video.
- Pair with (not replace by) an out-of-band verification process for
  high-risk actions requested over video call (wire transfers, credential
  resets, etc.) — see the accompanying threat model document.
- Evaluate commercial/vendor detection tools for production use; this
  prototype is best suited for internal awareness demos and as a starting
  point for a properly trained classifier.
