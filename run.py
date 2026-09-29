#!/usr/bin/env python3
"""
Laptop Price Tracker - one-file launcher for Windows, Linux and macOS.

Usage:   python run.py        (Windows: py run.py)
It creates a private virtual environment, installs requirements once,
starts the backend and the frontend, and opens the app in your browser.
Press Ctrl+C to stop everything.
"""
import hashlib
import os
import shutil
import socket
import subprocess
import sys
import time
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IS_WIN = os.name == "nt"
PLATFORM = "win" if IS_WIN else ("mac" if sys.platform == "darwin" else "linux")
VENV_DIR = ROOT / f".venv-{PLATFORM}"          # separate env per OS, so the folder can move between PCs
BIN = VENV_DIR / ("Scripts" if IS_WIN else "bin")
PY = BIN / ("python.exe" if IS_WIN else "python")
REQ = ROOT / "requirements.txt"
MARKER = VENV_DIR / ".requirements.sha256"

BACK_PORT = int(os.getenv("BACKEND_PORT", "8000"))
FRONT_PORT = int(os.getenv("FRONTEND_PORT", "8501"))


def say(msg):
    print(f"\n>> {msg}", flush=True)


def die(msg):
    print(f"\nERROR: {msg}", flush=True)
    sys.exit(1)


def port_in_use(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def ensure_env():
    if sys.version_info < (3, 10):
        die(f"Python 3.10 or newer is required (you have {sys.version.split()[0]}).")
    if not PY.exists():
        say(f"Creating virtual environment ({VENV_DIR.name})...")
        try:
            try:
                venv.EnvBuilder(with_pip=True, symlinks=not IS_WIN).create(VENV_DIR)
            except Exception:
                # e.g. running from a FAT/exFAT pendrive that can't do symlinks
                shutil.rmtree(VENV_DIR, ignore_errors=True)
                venv.EnvBuilder(with_pip=True, symlinks=False).create(VENV_DIR)
        except Exception as err:
            hint = "  On Ubuntu/Debian run: sudo apt install python3-venv" if not IS_WIN else ""
            die(f"Could not create the virtual environment: {err}\n{hint}")

    digest = hashlib.sha256(REQ.read_bytes()).hexdigest()
    if MARKER.exists() and MARKER.read_text().strip() == digest:
        return
    pip = [str(PY), "-m", "pip", "install", "--disable-pip-version-check"]
    wheels = ROOT / "wheelhouse"
    if wheels.is_dir() and any(wheels.glob("*.whl")):
        say("Installing packages from the offline 'wheelhouse' folder...")
        if subprocess.call(pip + ["--no-index", "--find-links", str(wheels), "-r", str(REQ)]) == 0:
            MARKER.write_text(digest)
            return
        say("Offline install was incomplete, trying the internet instead...")
    say("Installing packages (first run only, this can take a few minutes)...")
    if subprocess.call(pip + ["-r", str(REQ)]) != 0:
        die("Package install failed. Connect to the internet, or prepare the offline\n"
            "       'wheelhouse' folder at home first (see README.txt, option B).")
    MARKER.write_text(digest)


def ensure_model(py=None):
    """The .pkl model only loads on a matching scikit-learn version. If it doesn't, retrain it (takes seconds)."""
    py = py or PY
    model = ROOT / "backend" / "model" / "laptop_model.pkl"
    check = (
        "import warnings, joblib, pandas as pd\n"
        "warnings.simplefilter('error', UserWarning)\n"
        f"m = joblib.load(r'{model}')\n"
        "row = dict(Company='HP', TypeName='Notebook', CpuBrand='Intel Core i5', GpuBrand='Intel', OpSys='Windows 10',"
        " Inches=15.6, Ram=8, Weight=2.0, Touchscreen=0, IPS=0, SSD=256, HDD=0)\n"
        "m.predict(pd.DataFrame([row]))\n"
    )
    if subprocess.call([str(py), "-c", check], stderr=subprocess.DEVNULL) == 0:
        return
    say("Model file doesn't match this PC's scikit-learn version - retraining it (about a minute)...")
    if not (ROOT / "ml" / "laptop_price.csv").exists():
        die("ml/laptop_price.csv is missing, so the model can't be retrained.")
    if subprocess.call([str(py), "train.py"], cwd=ROOT / "ml") != 0:
        die("Retraining the model failed. Read the error above.")


def check_files():
    backend = ROOT / "backend"
    if not (backend / "serviceAccountKey.json").exists():
        die("backend/serviceAccountKey.json is missing (Firebase key). Put it in the backend folder.")
    env = backend / ".env"
    if not env.exists() or "SERPAPI_KEY" not in env.read_text(errors="ignore"):
        print("WARNING: backend/.env has no SERPAPI_KEY - the 'Compare prices' tab will return nothing.")


def wait_for_port(port, proc, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        if proc.poll() is not None:
            return False
        if port_in_use(port):
            return True
        time.sleep(0.5)
    return False


def stop(*procs):
    for p in procs:
        if p and p.poll() is None:
            p.terminate()
    for p in procs:
        if p:
            try:
                p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                p.kill()


def main():
    os.chdir(ROOT)
    check_files()
    ensure_env()
    ensure_model()

    if port_in_use(BACK_PORT):
        die(f"Port {BACK_PORT} is already in use. Close the other program or set BACKEND_PORT=8001.")
    if port_in_use(FRONT_PORT):
        die(f"Port {FRONT_PORT} is already in use. Close the other program or set FRONTEND_PORT=8502.")

    back = front = None
    try:
        say(f"Starting backend on port {BACK_PORT}...")
        back = subprocess.Popen(
            [str(PY), "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(BACK_PORT)],
            cwd=ROOT / "backend",
        )
        if not wait_for_port(BACK_PORT, back):
            stop(back)
            die("Backend did not start. Read the error above (often a missing key file or bad .env).")

        say(f"Starting app on http://localhost:{FRONT_PORT}  (Ctrl+C to stop)")
        env = dict(os.environ, LAPTOP_API=f"http://127.0.0.1:{BACK_PORT}")
        front = subprocess.Popen(
            [str(PY), "-m", "streamlit", "run", "app.py", "--server.port", str(FRONT_PORT),
             "--browser.gatherUsageStats", "false"],
            cwd=ROOT / "frontend", env=env,
        )
        while front.poll() is None and back.poll() is None:
            time.sleep(1)
        if back.poll() is not None:
            print("\nBackend stopped unexpectedly.")
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stop(front, back)


if __name__ == "__main__":
    main()
