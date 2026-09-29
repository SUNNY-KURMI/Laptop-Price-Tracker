LAPTOP PRICE TRACKER - PENDRIVE / COLLEGE LINUX PC GUIDE

WHAT YOU NEED ON THE COLLEGE PC
  - Python 3.10 or newer   (check: python3 --version)
  - VS Code (optional)
  - Internet on the first run  -- OR prepare offline packages at home (Option B)

OPTION A - COLLEGE PC HAS INTERNET
  1. Copy the whole "Laptop Price Tracker" folder from the pendrive to the
     PC's home folder (e.g. /home/yourname/). Do NOT run it from the pendrive:
     pendrives (FAT/exFAT) can't hold Python environments reliably.
  2. Open VS Code > File > Open Folder > choose "Laptop Price Tracker".
  3. Start it, either way:
       - Press Ctrl+Shift+B  (runs the "Run Laptop Price Tracker" task), or
       - Open the terminal (Ctrl+`) and type:   python3 run.py
  4. Wait. First run installs packages (a few minutes). The browser opens
     at http://localhost:8501.
  5. Press Ctrl+C in the terminal to stop.

  Next time it starts in seconds.

OPTION B - COLLEGE PC HAS NO INTERNET (prepare at home, once)
  1. On a PC with internet, open a terminal in this folder and run:
         python make_offline.py 3.12
     (use the Python version of the college PC instead of 3.12)
  2. A "wheelhouse" folder appears. Copy the whole project folder to the pendrive.
  3. At college, follow Option A. It installs from "wheelhouse" without internet.
  Note: "Compare prices" and "Price history" still need internet at run time
  (SerpAPI and Firebase). "Fair price check" works offline.

BEFORE FIRST USE CHECK THESE FILES
  backend/.env                   ->  SERPAPI_KEY=your_key
  backend/serviceAccountKey.json ->  your Firebase key

TROUBLESHOOTING
  "venv" error on Ubuntu/Debian  ->  sudo apt install python3-venv
  "Permission denied" on start.sh ->  use:  bash start.sh   (or python3 run.py)
  Port already in use            ->  BACKEND_PORT=8001 FRONTEND_PORT=8502 python3 run.py
  Model message on first run     ->  normal; it retrains to match this PC (about a minute)

KEEP THE PENDRIVE SAFE: it contains your API and Firebase keys.
