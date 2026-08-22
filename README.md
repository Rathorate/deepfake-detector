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

## Usage

Analyze a recorded video file:

```bash
python detector.py --input path/to/call_recording.mp4 --report report.json
```

Analyze a live webcam feed (press `q` to stop and see the report):

```bash
python detector.py --webcam
```

Optional flags:

```bash
python detector.py --webcam --camera-index 1 --seconds 30 --report report.json
python detector.py --input video.mp4 --show   # preview window while analyzing a file
```

## Output

A JSON report with per-metric statistics, an overall suspicion level, and
plain-language flags explaining what was detected, e.g.:

```json
{
  "suspicion_level": "medium",
  "suspicion_points": 2,
  "flags": [
    "Abnormally low blink rate detected (0.0/min) — ...",
    "Face-boundary blending looks unusually smooth/uniform ..."
  ]
}
```

## Suggested next steps for a real security initiative

- Validate against labeled datasets and tune thresholds before any
  operational use.
- Pair with (not replace by) an out-of-band verification process for
  high-risk actions requested over video call (wire transfers, credential
  resets, etc.) — see the accompanying threat model document.
- Evaluate commercial/vendor detection tools for production use; this
  prototype is best suited for internal awareness demos and as a starting
  point for a properly trained classifier.
