"""Download wheels for PySide6/requests/pytest directly from PyPI JSON API,
bypassing pip's network stack (which stalls on this machine's network)."""
import json
import os
import sys
import urllib.request

DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wheelhouse")
os.makedirs(DEST, exist_ok=True)

# package -> filename substring matcher (prefer cp311 win_amd64, else py3-none-any)
PACKAGES = ["PySide6-Essentials", "PySide6-Addons", "shiboken6",
            "requests", "urllib3", "idna", "charset-normalizer", "certifi",
            "pytest", "pluggy", "iniconfig", "packaging", "colorama", "Pygments",
            "pyinstaller", "pyinstaller-hooks-contrib", "altgraph", "pefile",
            "pywin32-ctypes", "setuptools"]


def pick_wheel(name: str) -> str | None:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json", timeout=30) as r:
        data = json.load(r)
    # latest version files
    for f in data["urls"]:
        fn = f["filename"]
        if not fn.endswith(".whl"):
            continue
        if "py3-none-any" in fn or "win_amd64" in fn:
            return f["url"], fn
    return None


def download(url: str, path: str) -> None:
    if os.path.exists(path) and os.path.getsize(path) > 0:
        print("skip", os.path.basename(path))
        return
    print("downloading", os.path.basename(path), flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "pip/24"})
    with urllib.request.urlopen(req, timeout=60) as r, open(path + ".part", "wb") as out:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    os.replace(path + ".part", path)
    print("done", os.path.basename(path), os.path.getsize(path) // 1024, "KB", flush=True)


failed = []
for pkg in PACKAGES:
    try:
        got = pick_wheel(pkg)
        if not got:
            print("NO WHEEL for", pkg)
            failed.append(pkg)
            continue
        url, fn = got
        download(url, os.path.join(DEST, fn))
    except Exception as e:
        print("FAIL", pkg, e)
        failed.append(pkg)

print("FAILED:", failed)
sys.exit(1 if failed else 0)
