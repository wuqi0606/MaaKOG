"""Bundle a portable Python + maafw into the install directory (win-x86_64 only).

Run inside CI on ubuntu: downloads Windows Python embeddable and Windows maafw
wheels, assembles them into install/python so end users need no Python install.
"""

import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

PYTHON_VERSION = "3.13.17"
MAAFW_VERSION = "5.16.1"
PY_TAG = "313"

PYTHON_URL = (
    f"https://www.python.org/ftp/python/{PYTHON_VERSION}/"
    f"python-{PYTHON_VERSION}-embed-amd64.zip"
)


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "MaaAOT-build"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)
    print(f"downloaded {url} -> {dest} ({os.path.getsize(dest)} bytes)")


def main():
    install_python = sys.argv[1]
    tmp = tempfile.mkdtemp(prefix="maaot-python-")
    try:
        py_zip = os.path.join(tmp, "python.zip")
        download(PYTHON_URL, py_zip)
        with zipfile.ZipFile(py_zip) as z:
            z.extractall(install_python)
        print(f"extracted Python embeddable -> {install_python}")

        # Enable site-packages in the embeddable python.
        pth = os.path.join(install_python, f"python{PY_TAG}._pth")
        with open(pth, "rb") as f:
            content = f.read().decode("utf-8")
        content = content.replace("#import site", "import site")
        with open(pth, "wb") as f:
            f.write(content.encode("utf-8"))
        print(f"enabled import site in {pth}")

        # Download Windows wheels (ubuntu host cannot pip-install win wheels,
        # but a wheel is just a zip we can extract into site-packages).
        wheel_dir = os.path.join(tmp, "wheels")
        os.makedirs(wheel_dir, exist_ok=True)
        import subprocess

        subprocess.run(
            [
                sys.executable, "-m", "pip", "download",
                f"maafw=={MAAFW_VERSION}",
                "--platform", "win_amd64",
                "--python-version", PY_TAG,
                "--implementation", "cp",
                "--abi", f"cp{PY_TAG}",
                "--only-binary", ":all:",
                "-d", wheel_dir,
            ],
            check=True,
        )
        site = os.path.join(install_python, "Lib", "site-packages")
        os.makedirs(site, exist_ok=True)
        for name in sorted(os.listdir(wheel_dir)):
            if name.endswith(".whl"):
                with zipfile.ZipFile(os.path.join(wheel_dir, name)) as z:
                    z.extractall(site)
                print(f"extracted wheel {name}")
        print("bundled Python + maafw ready")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
