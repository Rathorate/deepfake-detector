"""
Web front-end for the deepfake artifact detector.

Wraps the same DeepfakeArtifactDetector used by detector.py behind a small
Flask app with two input paths:
  - Upload a video file
  - Record a short webcam clip in the browser and submit it (liveness check)

Both paths end up analyzing a video file the same way, so results are
consistent between the CLI tool and this web UI.

SECURITY: this app is protected by HTTP Basic Auth. Set APP_USERNAME and
APP_PASSWORD environment variables before running -- do NOT deploy this
with the default credentials. See README.md for deployment instructions.
"""

import os
import secrets
import tempfile
from functools import wraps

import cv2
from flask import Flask, render_template, request, jsonify, Response

from detector import DeepfakeArtifactDetector

app = Flask(__name__)

# Cap uploads at 200 MB to avoid someone accidentally (or deliberately)
# uploading something huge and exhausting disk/memory on the host.
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm"}


# ---------------------------------------------------------------------------
# Basic Auth
# ---------------------------------------------------------------------------

def _check_auth(username, password):
    expected_user = os.environ.get("APP_USERNAME")
    expected_pass = os.environ.get("APP_PASSWORD")
    if not expected_user or not expected_pass:
        # Fail closed: if credentials aren't configured, refuse all access
        # rather than silently allowing anyone in.
        return False
    return secrets.compare_digest(username or "", expected_user) and \
        secrets.compare_digest(password or "", expected_pass)


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not _check_auth(auth.username, auth.password):
            return Response(
                "Authentication required.", 401,
                {"WWW-Authenticate": 'Basic realm="Deepfake Detector"'},
            )
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Analysis helper (mirrors detector.py's run_on_video_file, but returns
# the summary dict instead of printing it)
# ---------------------------------------------------------------------------

def analyze_video_file(path):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError("Could not open the uploaded video file.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    detector = DeepfakeArtifactDetector()
    frame_idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        detector.process_frame(frame)
        frame_idx += 1
        # Safety cap: don't analyze more than ~2000 frames (roughly a
        # couple of minutes at 15-30fps) to keep response times reasonable
        # on a modest server.
        if frame_idx >= 2000:
            break

    cap.release()
    duration_sec = frame_idx / fps if fps else 0.0
    return detector.summarize(duration_sec)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
@requires_auth
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
@requires_auth
def analyze():
    if "video" not in request.files:
        return jsonify({"error": "No video file provided."}), 400

    file = request.files["video"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    # Webcam recordings arrive as a blob without a normal filename/extension
    # in some browsers; allow those through and default to .webm.
    suffix = ".webm"
    if file.filename and allowed_file(file.filename):
        suffix = "." + file.filename.rsplit(".", 1)[1].lower()
    elif file.filename and not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type."}), 400

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        summary = analyze_video_file(tmp_path)
        return jsonify(summary)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.route("/healthz")
def healthz():
    # Unauthenticated health check for deployment platforms.
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    if not os.environ.get("APP_USERNAME") or not os.environ.get("APP_PASSWORD"):
        print(
            "WARNING: APP_USERNAME / APP_PASSWORD environment variables are "
            "not set. The app will refuse all requests until you set them.\n"
            "Example:\n"
            "  export APP_USERNAME=admin\n"
            "  export APP_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(16))')\n"
        )
    app.run(host="127.0.0.1", port=5000, debug=False)
