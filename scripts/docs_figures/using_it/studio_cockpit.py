"""Studio cockpit screenshot with four-zone annotations (Playwright)."""

from __future__ import annotations

import atexit
import os
import subprocess
import time
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[3]
WEB = REPO_ROOT / "web"
FIGURES_DIR = REPO_ROOT / "docs" / "public" / "figures"

_vite_proc: subprocess.Popen[bytes] | None = None


def _cleanup_vite() -> None:
    global _vite_proc
    if _vite_proc is not None and _vite_proc.poll() is None:
        _vite_proc.terminate()
        try:
            _vite_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _vite_proc.kill()
    _vite_proc = None


def _ensure_wasm() -> None:
    wasm_dir = WEB / "src" / "wasm"
    if not wasm_dir.is_dir() or not list(wasm_dir.glob("*.wasm")):
        subprocess.run(
            ["./scripts/build-wasm.sh"],
            cwd=REPO_ROOT,
            check=True,
        )


def _start_vite(port: int) -> subprocess.Popen[bytes]:
    global _vite_proc
    env = os.environ.copy()
    env["VITE_ENGINE_ADAPTER"] = "wasm"
    env["PW_E2E"] = "1"
    _vite_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", str(port), "--strictPort"],
        cwd=WEB,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    atexit.register(_cleanup_vite)
    return _vite_proc


def _wait_for_server(url: str, timeout_s: float = 60.0) -> None:
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5)
    raise RuntimeError(f"Vite dev server did not start at {url}")


def _capture_screenshot(port: int, raw_path: Path) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(
            f"http://localhost:{port}/", wait_until="domcontentloaded", timeout=60000
        )
        page.wait_for_selector(".cockpit-grid", state="visible", timeout=30000)
        page.wait_for_function(
            "() => document.querySelector('#engine-status')"
            "?.getAttribute('data-status') !== 'loading'",
            timeout=20000,
        )
        page.wait_for_timeout(500)
        page.screenshot(path=str(raw_path), full_page=True)
        browser.close()


def _annotate(raw_path: Path, out_name: str, out_dir: Path | None = None) -> Path:
    img = mpimg.imread(raw_path)
    fig, ax = plt.subplots(figsize=(img.shape[1] / 100, img.shape[0] / 100), dpi=100)
    ax.imshow(img)
    ax.axis("off")
    zones = [
        (0.02, 0.52, 0.46, 0.44, "Metrics column"),
        (0.50, 0.52, 0.30, 0.44, "Belief column"),
        (0.81, 0.52, 0.17, 0.44, "Sidebar"),
        (0.02, 0.02, 0.96, 0.46, "Tuning dock"),
    ]
    for x, y, w, h, label in zones:
        ax.add_patch(
            Rectangle(
                (x, y),
                w,
                h,
                fill=False,
                edgecolor="#c44e52",
                lw=3,
                transform=ax.transAxes,
            )
        )
        ax.text(
            x + 0.01,
            y + h - 0.01,
            label,
            color="#c44e52",
            fontsize=13,
            fontweight="bold",
            transform=ax.transAxes,
            va="top",
        )
    target_dir = out_dir or FIGURES_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / out_name
    fig.savefig(out_path, dpi=120, bbox_inches="tight", facecolor="white", pad_inches=0)
    plt.close(fig)
    return out_path


def render(out_dir: Path | None = None) -> Path:
    port = int(os.environ.get("DOCS_FIGURES_STUDIO_PORT", "5199"))
    target_dir = out_dir or FIGURES_DIR
    _ensure_wasm()
    proc = _start_vite(port)
    if proc.poll() is not None:
        raise RuntimeError("Vite dev server failed to start")
    _wait_for_server(f"http://localhost:{port}/")
    raw_path = target_dir / "_studio_cockpit_raw.png"
    try:
        _capture_screenshot(port, raw_path)
        return _annotate(raw_path, "studio-cockpit-annotated.png", target_dir)
    finally:
        _cleanup_vite()
        raw_path.unlink(missing_ok=True)


if __name__ == "__main__":
    render()
