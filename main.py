"""Start SUNDAY and its Python backend."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

def main():
    frontend = ROOT / "sunday"
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        print("Install Node.js including npm, then run python main.py again.")
        return 1
    env = os.environ.copy()
    env.pop("ELECTRON_RUN_AS_NODE", None)
    env["SUNDAY_PYTHON"] = sys.executable
    env["SUNDAY_BACKEND_ROOT"] = str(ROOT)
    if not (frontend / "node_modules/electron/dist").is_dir():
        subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=frontend, env=env, check=True)
    sources = [frontend / "package.json", frontend / "vite.config.ts"]
    for folder in ("src", "electron", "scripts"):
        sources.extend(p for p in (frontend / folder).rglob("*") if p.is_file())
    outputs = [frontend / "dist/index.html", frontend / "dist-electron/main.cjs", frontend / "dist-electron/preload.cjs"]
    if any(not p.exists() for p in outputs) or max(p.stat().st_mtime for p in sources) > min(p.stat().st_mtime for p in outputs):
        subprocess.run([npm, "run", "build"], cwd=frontend, env=env, check=True)
    electron = frontend / "node_modules/electron/dist" / ("electron.exe" if os.name == "nt" else "electron")
    process = subprocess.Popen([str(electron), str(frontend)], cwd=ROOT, env=env)
    try:
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        return process.wait()

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"SUNDAY could not start: {exc}", file=sys.stderr)
        sys.exit(1)
