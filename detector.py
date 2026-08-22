"""
Deepfake Video Call Detection Prototype
----------------------------------------
Heuristic, artifact-based deepfake detector for internal security research /
employee-awareness tooling.

IMPORTANT LIMITATIONS (read before relying on this for anything):
  - This is a heuristic proof-of-concept, NOT a trained deep-learning
    classifier. It looks for known low-level artifacts common in face-swap
    and reenactment pipelines (blink irregularity, face-boundary blending
    seams, temporal flicker, face-region jitter).
  - It uses OpenCV's built-in Haar cascade detectors (shipped with
    opencv-python, no external model download required) rather than a
    precise facial-landmark model, so its signals are coarser than a
    landmark-based or trained-classifier approach.
  - It will have false positives (e.g. poor webcam, bad lighting, low
    bitrate video calls) and false negatives (high-quality modern deepfakes
    can evade all of these heuristics).
  - It should NOT be used as the sole basis for a security decision
    ("this call is/isn't a deepfake"). Use it as one signal among many,
    and validate it against labeled datasets (FaceForensics++, DFDC,
    Celeb-DF) before treating its output as authoritative.
  - For production-grade detection, evaluate commercial/vendor solutions
    or train a dedicated classifier on labeled data.

Usage:
    python detector.py --input path/to/video.mp4
    python detector.py --webcam
    python detector.py --webcam --camera-index 1
    python detector.py --input video.mp4 --report out_report.json
"""

import argparse
import json
import time
import sys
from dataclasses import dataclass, field

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Cascade classifiers (bundled with opencv-python, no download required)
# ---------------------------------------------------------------------------
FACE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
EYE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_eye.xml"


@dataclass
class FrameMetrics:
    face_bbox: tuple = None
    eyes_detected: int = None
    boundary_score: float = None
    flicker_score: float = None
    bbox_center: tuple = None


@dataclass
class SessionStats:
    frame_count: int = 0
    frames_with_face: int = 0
    closed_eye_run: int = 0
    blink_count: int = 0
    eyes_detected_history: list = field(default_factory=list)
    boundary_scores: list = field(default_factory=list)
    flicker_scores: list = field(default_factory=list)
    bbox_centers: list = field(default_factory=list)
    bbox_sizes: list = field(default_factory=list)


class DeepfakeArtifactDetector:
    """Runs a sliding-window heuristic analysis over a video stream.

    Uses classical CV (Haar cascades + gradient/frame-diff analysis)
    rather than a trained neural classifier, so it is portable and needs
    no model downloads -- but is correspondingly coarser. See module
    docstring for limitations.
    """

    def __init__(self, blink_consec_frames=2):
        self.blink_consec_frames = blink_consec_frames
        self.face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)
        self.eye_cascade = cv2.CascadeClassifier(EYE_CASCADE_PATH)
        if self.face_cascade.empty() or self.eye_cascade.empty():
            raise RuntimeError(
                "Could not load OpenCV Haar cascade files. Check your "
                "opencv-python installation."
            )

        self.stats = SessionStats()
        self._prev_gray_face = None

    # -- per-frame analysis ------------------------------------------------

    def _detect_face(self, gray):
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=6, minSize=(80, 80)
        )
        if len(faces) == 0:
            return None
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, fw, fh = faces[0]
        return (int(x), int(y), int(x + fw), int(y + fh))

    def _count_eyes(self, gray, bbox):
        x0, y0, x1, y1 = bbox
        roi = gray[y0:y0 + int((y1 - y0) * 0.6), x0:x1]
        if roi.size == 0:
            return 0
        eyes = self.eye_cascade.detectMultiScale(
            roi, scaleFactor=1.1, minNeighbors=6, minSize=(15, 15)
        )
        return len(eyes)

    def _boundary_blend_score(self, gray, bbox):
        """
        Approximates face/background blending-seam artifacts by measuring
        edge-gradient irregularity along an elliptical ring at the face
        boundary. Natural skin-to-background transitions tend to have
        moderately consistent gradients; many face-swap composites show
        unnaturally uniform or unnaturally sharp gradients right at the
        mask edge.
        """
        x0, y0, x1, y1 = bbox
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        ax, ay = max(1, (x1 - x0) // 2), max(1, (y1 - y0) // 2)

        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.ellipse(mask, (cx, cy), (ax, ay), 0, 0, 360, 255, -1)
        ring = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, np.ones((11, 11), np.uint8))

        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag = np.sqrt(sobel_x ** 2 + sobel_y ** 2)

        ring_pixels = grad_mag[ring > 0]
        if ring_pixels.size == 0:
            return None
        mean, std = ring_pixels.mean(), ring_pixels.std()
        cv_score = std / (mean + 1e-6)
        return float(cv_score)

    def _flicker_score(self, gray, bbox):
        x0, y0, x1, y1 = bbox
        if x1 <= x0 or y1 <= y0:
            return None
        face_crop = cv2.resize(gray[y0:y1, x0:x1], (128, 128))
        score = None
        if self._prev_gray_face is not None:
            diff = cv2.absdiff(face_crop, self._prev_gray_face)
            score = float(np.mean(diff))
        self._prev_gray_face = face_crop
        return score

    def process_frame(self, frame_bgr):
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        self.stats.frame_count += 1
        metrics = FrameMetrics()

        bbox = self._detect_face(gray)
        if bbox is None:
            self._prev_gray_face = None
            return metrics

        self.stats.frames_with_face += 1
        metrics.face_bbox = bbox
        x0, y0, x1, y1 = bbox
        metrics.bbox_center = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        self.stats.bbox_centers.append(metrics.bbox_center)
        self.stats.bbox_sizes.append((x1 - x0) * (y1 - y0))

        eyes = self._count_eyes(gray, bbox)
        metrics.eyes_detected = eyes
        self.stats.eyes_detected_history.append(eyes)
        if eyes < 2:
            self.stats.closed_eye_run += 1
        else:
            if self.stats.closed_eye_run >= self.blink_consec_frames:
                self.stats.blink_count += 1
            self.stats.closed_eye_run = 0

        boundary_score = self._boundary_blend_score(gray, bbox)
        metrics.boundary_score = boundary_score
        if boundary_score is not None:
            self.stats.boundary_scores.append(boundary_score)

        flicker = self._flicker_score(gray, bbox)
        metrics.flicker_score = flicker
        if flicker is not None:
            self.stats.flicker_scores.append(flicker)

        return metrics

    # -- session summary -----------------------------------------------

    def summarize(self, duration_sec):
        s = self.stats
        face_coverage = s.frames_with_face / max(1, s.frame_count)
        blink_rate_per_min = (
            (s.blink_count / duration_sec) * 60.0 if duration_sec > 0 else 0.0
        )

        def _stat(arr):
            if not arr:
                return {"mean": None, "std": None}
            a = np.array(arr)
            return {"mean": float(a.mean()), "std": float(a.std())}

        boundary_stat = _stat(s.boundary_scores)
        flicker_stat = _stat(s.flicker_scores)

        jitter_scores = []
        for i in range(1, len(s.bbox_centers)):
            c0, c1 = s.bbox_centers[i - 1], s.bbox_centers[i]
            dist = np.hypot(c1[0] - c0[0], c1[1] - c0[1])
            size = np.sqrt(max(1.0, s.bbox_sizes[i]))
            jitter_scores.append(float(dist / size))
        jitter_stat = _stat(jitter_scores)

        flags = []
        suspicion_points = 0

        if s.frame_count > duration_sec * 5:
            if blink_rate_per_min < 4:
                flags.append(
                    "Abnormally low blink rate detected "
                    f"({blink_rate_per_min:.1f}/min) — a known artifact in "
                    "some face-swap pipelines trained on datasets with few "
                    "closed-eye frames. Note: Haar-cascade eye detection is "
                    "coarse and can under-count blinks on its own, so treat "
                    "this signal as weak evidence, not proof."
                )
                suspicion_points += 1
            elif blink_rate_per_min > 45:
                flags.append(
                    "Abnormally high / erratic blink rate detected "
                    f"({blink_rate_per_min:.1f}/min)."
                )
                suspicion_points += 1

        if boundary_stat["mean"] is not None and boundary_stat["mean"] < 15:
            flags.append(
                "Face-boundary blending looks unusually smooth/uniform "
                "(low gradient variance along the boundary ring) — "
                "consistent with a composited/blended face mask."
            )
            suspicion_points += 1

        if flicker_stat["std"] is not None and flicker_stat["std"] > 8:
            flags.append(
                "High frame-to-frame flicker in the face region — "
                "consistent with temporal inconsistency seen in some "
                "reenactment/face-swap outputs."
            )
            suspicion_points += 1

        if jitter_stat["mean"] is not None and jitter_stat["mean"] > 0.05:
            flags.append(
                "Face position/size shows more frame-to-frame jitter than "
                "expected for natural motion — possible sign of unstable "
                "synthesis or tracking artifacts."
            )
            suspicion_points += 1

        if face_coverage < 0.5:
            flags.append(
                "Face was only reliably detected in "
                f"{face_coverage*100:.0f}% of frames — results below are "
                "low-confidence; re-run with better lighting/framing."
            )

        max_points = 4
        suspicion_level = (
            "low" if suspicion_points == 0 else
            "medium" if suspicion_points <= 2 else
            "high"
        )

        return {
            "frame_count": s.frame_count,
            "frames_with_face": s.frames_with_face,
            "face_coverage_pct": round(face_coverage * 100, 1),
            "duration_sec": round(duration_sec, 2),
            "blink_count": s.blink_count,
            "blink_rate_per_min": round(blink_rate_per_min, 2),
            "boundary_blend_stat": boundary_stat,
            "flicker_stat": flicker_stat,
            "bbox_jitter_stat": jitter_stat,
            "suspicion_points": suspicion_points,
            "suspicion_points_max": max_points,
            "suspicion_level": suspicion_level,
            "flags": flags,
            "disclaimer": (
                "Heuristic, classical-CV artifact analysis only (Haar "
                "cascades + gradient/frame-diff signals). Not a trained "
                "classifier and not landmark-precise. Validate against "
                "labeled datasets (FaceForensics++, DFDC, Celeb-DF) before "
                "relying on this for real decisions. False positives are "
                "common with low-quality webcams/compression; false "
                "negatives are common with high-quality modern deepfakes."
            ),
        }


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

def run_on_video_file(path, show=False, report_path=None):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"ERROR: could not open video file: {path}", file=sys.stderr)
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    detector = DeepfakeArtifactDetector()
    frame_idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        detector.process_frame(frame)
        frame_idx += 1
        if show:
            cv2.imshow("deepfake_detector (press q to quit)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    if show:
        cv2.destroyAllWindows()

    duration_sec = frame_idx / fps if fps else 0.0
    summary = detector.summarize(duration_sec)
    _emit_report(summary, report_path)


def run_on_webcam(camera_index=0, seconds=None, report_path=None):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"ERROR: could not open webcam index {camera_index}", file=sys.stderr)
        sys.exit(1)

    detector = DeepfakeArtifactDetector()
    start = time.time()
    print("Recording from webcam. Press 'q' to stop and see the report.")

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        metrics = detector.process_frame(frame)

        display = frame.copy()
        if metrics.face_bbox is not None:
            x0, y0, x1, y1 = metrics.face_bbox
            cv2.rectangle(display, (x0, y0), (x1, y1), (0, 255, 0), 2)
        if metrics.eyes_detected is not None:
            cv2.putText(display, f"eyes: {metrics.eyes_detected}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(display, "Press 'q' to stop", (10, display.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.imshow("deepfake_detector (press q to quit)", display)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        if seconds is not None and (time.time() - start) > seconds:
            break

    cap.release()
    cv2.destroyAllWindows()

    duration_sec = time.time() - start
    summary = detector.summarize(duration_sec)
    _emit_report(summary, report_path)


def _emit_report(summary, report_path):
    print("\n" + "=" * 60)
    print("DEEPFAKE ARTIFACT ANALYSIS REPORT")
    print("=" * 60)
    print(json.dumps(summary, indent=2))
    print("=" * 60)
    print(f"Suspicion level: {summary['suspicion_level'].upper()} "
          f"({summary['suspicion_points']}/{summary['suspicion_points_max']} signals)")
    if summary["flags"]:
        print("\nFlags raised:")
        for f in summary["flags"]:
            print(f"  - {f}")
    else:
        print("\nNo artifact flags raised.")
    print(f"\n{summary['disclaimer']}")

    if report_path:
        with open(report_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nFull report written to: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Heuristic deepfake artifact detector (video call security research)."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", help="Path to a video file to analyze.")
    src.add_argument("--webcam", action="store_true", help="Analyze live webcam feed.")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--seconds", type=float, default=None,
                        help="Max seconds to record from webcam (default: until 'q').")
    parser.add_argument("--show", action="store_true",
                        help="Show video preview window while analyzing a file.")
    parser.add_argument("--report", dest="report_path", default=None,
                        help="Path to write the JSON report to.")
    args = parser.parse_args()

    if args.input:
        run_on_video_file(args.input, show=args.show, report_path=args.report_path)
    else:
        run_on_webcam(args.camera_index, seconds=args.seconds, report_path=args.report_path)


if __name__ == "__main__":
    main()
