"""
Materials DMP - Single command launcher.

Usage:
    python run.py          # Start both backend and frontend
    python run.py backend  # Start backend only
    python run.py frontend # Start frontend only
    python run.py init     # Initialize database only
"""

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent


def find_npm():
    """Find npm executable, trying multiple approaches. Returns full path."""
    # Try where command first — get full path
    for cmd in ["npm.cmd", "npm"]:
        try:
            result = subprocess.run(["where", cmd], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                full_path = result.stdout.strip().split("\n")[0].strip()
                if Path(full_path).exists():
                    return full_path
        except Exception:
            pass

    # Try finding npm next to node.exe
    try:
        node_result = subprocess.run(["where", "node"], capture_output=True, text=True)
        if node_result.returncode == 0:
            node_dir = Path(node_result.stdout.strip().split("\n")[0]).parent
            for name in ["npm.cmd", "npm"]:
                p = node_dir / name
                if p.exists():
                    return str(p)
    except Exception:
        pass

    return None


def check_prerequisites():
    """Verify Python and Node.js are available."""
    try:
        subprocess.run([sys.executable, "--version"], capture_output=True, check=True)
    except Exception:
        print("[ERROR] Python not found")
        sys.exit(1)

    npm = find_npm()
    if npm is None:
        print("[ERROR] Cannot find npm. Please install Node.js from https://nodejs.org/")
        sys.exit(1)

    return npm



def setup_venv():
    """Create virtual environment if missing."""
    venv_dir = ROOT / "venv"
    if not venv_dir.exists():
        print("[1/4] Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)


def get_python():
    """Return path to venv Python."""
    if os.name == "nt":
        return str(ROOT / "venv" / "Scripts" / "python.exe")
    return str(ROOT / "venv" / "bin" / "python")


def install_deps():
    """Install backend dependencies."""
    pip = get_python()
    print("[2/4] Installing backend dependencies...")
    env = os.environ.copy()
    # Clear proxy settings
    for var in ["ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "SOCKS_PROXY"]:
        env.pop(var, None)
    subprocess.run(
        [pip, "-m", "pip", "install", "-q",
         "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
         "--trusted-host", "pypi.tuna.tsinghua.edu.cn",
         "-r", str(ROOT / "backend" / "requirements.txt")],
        env=env, check=True,
    )


def init_db():
    """Initialize database with roles and demo data."""
    pip = get_python()
    print("[3/4] Initializing database (SQLite)...")
    backend = str(ROOT / "backend")
    subprocess.run([pip, "-m", "scripts.init_roles"], cwd=backend, check=True)
    subprocess.run([pip, "-m", "scripts.seed_data"], cwd=backend, check=True)


def start_backend():
    """Start FastAPI backend."""
    pip = get_python()
    backend = str(ROOT / "backend")
    print("Starting backend on http://localhost:8000 ...")
    return subprocess.Popen(
        [pip, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=backend,
    )


def start_frontend(npm):
    """Start Vite frontend dev server."""
    frontend = str(ROOT / "frontend")

    print("[4/4] Installing frontend dependencies...")
    subprocess.run(
        [npm, "config", "set", "registry", "https://registry.npmmirror.com"],
        cwd=frontend, check=True,
    )
    subprocess.run([npm, "install"], cwd=frontend, check=True)

    print("Starting frontend on http://localhost:5173 ...")
    return subprocess.Popen(
        [npm, "run", "dev"],
        cwd=frontend,
    )


def main():
    npm = check_prerequisites()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    if cmd == "init":
        setup_venv()
        install_deps()
        init_db()
        print("Database initialized. Run 'python run.py' to start.")
        return

    if cmd == "backend":
        setup_venv()
        install_deps()
        init_db()
        proc = start_backend()
        print("Backend running. Press Ctrl+C to stop.")
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
        return

    if cmd == "frontend":
        proc = start_frontend(npm)
        print("Frontend running. Press Ctrl+C to stop.")
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
        return

    # Default: start everything
    setup_venv()
    install_deps()
    init_db()
    backend_proc = start_backend()

    # Wait for backend to be ready
    print("Waiting for backend...", end="", flush=True)
    for _ in range(15):
        time.sleep(1)
        print(".", end="", flush=True)
        try:
            from urllib.request import urlopen
            urlopen("http://localhost:8000/health", timeout=2)
            print(" OK!")
            break
        except Exception:
            pass
    else:
        print(" timeout")
        print("[WARNING] Backend did not respond. Check for errors above.")
        backend_proc.terminate()
        sys.exit(1)

    frontend_proc = start_frontend(npm)

    print()
    print("=" * 44)
    print("  Backend API:  http://localhost:8000")
    print("  API Docs:     http://localhost:8000/api/v1/docs")
    print("  Frontend:     http://localhost:5173")
    print("  Login:        admin / admin123")
    print("=" * 44)
    print()
    print("Press Ctrl+C to stop all services.")

    webbrowser.open("http://localhost:5173")

    try:
        backend_proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        backend_proc.terminate()
        frontend_proc.terminate()
        print("Stopped.")


if __name__ == "__main__":
    main()
