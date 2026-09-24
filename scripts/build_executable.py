#!/usr/bin/env python3
"""Automated one-command packaging pipeline for Say It Windows Desktop Application.

1. Builds the React frontend via Vite into dist/index.html.
2. Generates multi-resolution say_it.ico from the brand asset.
3. Packages the application with PyInstaller into release/SayIt/SayIt.exe.
4. Generates a release zip archive ready to upload to the website.
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def step(msg: str):
    print(f"\n========================================================")
    print(f"  {msg}")
    print(f"========================================================")


def run_cmd(cmd: list[str], cwd: Path | None = None):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd or ROOT), shell=False)
    if result.returncode != 0:
        print(f"ERROR: Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)


def main():
    step("1. Building React Frontend Bundle (Single File)")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    run_cmd([npm_cmd, "run", "build"], cwd=ROOT)

    built_html = ROOT / "dist" / "index.html"
    if not built_html.exists():
        print(f"ERROR: Expected {built_html} to exist after build.")
        sys.exit(1)
    print(f"Frontend built successfully ({built_html.stat().st_size // 1024} KB)")

    step("2. Verifying Windows Application Icon (say_it.ico)")
    icon_path = ROOT / "say_it.ico"
    if not icon_path.exists():
        try:
            from PIL import Image
            logo = Image.open(ROOT / "src" / "assets" / "brand_logo_mark.png").convert("RGBA")
            logo.save(icon_path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            print("Generated say_it.ico successfully.")
        except Exception as e:
            print(f"Warning: Icon generation failed ({e}), continuing without custom icon.")

    step("3. Compiling Desktop Executable via PyInstaller")
    py_exec = sys.executable

    release_dir = ROOT / "release"
    work_dir = ROOT / "build_cache"

    app_target_dir = release_dir / "SayIt"
    if app_target_dir.exists():
        try:
            shutil.rmtree(app_target_dir)
        except Exception as e:
            print(f"Notice: Failed to remove previous release folder ({e}), proceeding with --noconfirm.")

    pyinstaller_args = [
        py_exec,
        "-m", "PyInstaller",
        "--name=SayIt",
        "--noconfirm",
        "--windowed",
        "--noconsole",
        "--clean",
        f"--distpath={release_dir}",
        f"--workpath={work_dir}",
        f"--add-data={ROOT / 'dist'}{os.pathsep}dist",
        "--hidden-import=webview",
        "--hidden-import=webview.platforms.winforms",
        "--hidden-import=clr_loader",
        "--hidden-import=pythonnet",
        "--hidden-import=sounddevice",
        "--hidden-import=soxr",
        "--hidden-import=ctranslate2",
        "--hidden-import=faster_whisper",
        # faster_whisper ships a bundled Silero VAD .onnx + data used at runtime by
        # model.transcribe(vad_filter=True); PyInstaller doesn't grab data files
        # from hidden-imports, so collect them explicitly or frozen local STT throws.
        # NOTE: frozen GPU STT would additionally need the nvidia cuBLAS/cuDNN bin
        # DLLs bundled (e.g. --collect-binaries=nvidia.cublas / nvidia.cudnn); left
        # out to keep the exe small — CPU int8 fallback works without them.
        "--collect-data=faster_whisper",
        "--collect-data=ctranslate2",
        "--hidden-import=keyboard",
        "--hidden-import=mouse",
        "--hidden-import=pyperclip",
        "--hidden-import=winsound",
        "--hidden-import=numpy",
    ]

    assets_sounds = ROOT / "wisper" / "assets"
    if assets_sounds.exists():
        pyinstaller_args.append(f"--add-data={assets_sounds}{os.pathsep}wisper/assets")

    if icon_path.exists():
        pyinstaller_args.append(f"--icon={icon_path}")

    pyinstaller_args.append(str(ROOT / "run_app.py"))

    run_cmd(pyinstaller_args, cwd=ROOT)

    exe_path = release_dir / "SayIt" / "SayIt.exe"
    if not exe_path.exists():
        print(f"ERROR: Expected executable at {exe_path}")
        sys.exit(1)

    print(f"Success! Executable created at: {exe_path}")

    # Copy .env and config.json into release directory so portable distribution works out-of-the-box
    app_folder = release_dir / "SayIt"
    if (ROOT / ".env").exists():
        shutil.copy2(ROOT / ".env", app_folder / ".env")
        print("Copied .env to release folder.")
    if (ROOT / "config.json").exists():
        shutil.copy2(ROOT / "config.json", app_folder / "config.json")
        print("Copied config.json to release folder.")

    step("4. Creating Release Zip Package for Website Publishing")
    zip_output = release_dir / "SayIt-v1.0.0-windows-x64.zip"
    if zip_output.exists():
        zip_output.unlink()
    with zipfile.ZipFile(zip_output, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in app_folder.rglob("*"):
            arcname = Path("SayIt") / file.relative_to(app_folder)
            zf.write(file, arcname)

    print(f"Release package ready: {zip_output} ({zip_output.stat().st_size // (1024 * 1024)} MB)")

    # Also copy the zip to the website's public directory if it exists
    website_public = ROOT.parent / "SayIT_Web" / "public"
    if website_public.exists():
        try:
            target_dest = website_public / "SayIt-v1.0.0-windows-x64.zip"
            shutil.copy2(zip_output, target_dest)
            print(f"Automatically linked to website public folder at: {target_dest}")
        except Exception as e:
            print(f"Note: Could not auto-copy to website public folder ({e})")

    step("PUBLISH READY!")
    print(f"""
Your app is fully compiled and ready for release!

Files generated:
1. Executable Folder:
   {exe_path.parent}
   Run SayIt.exe directly by double-clicking it.

2. Release Zip (to link on your website download button):
   {zip_output}
""")


if __name__ == "__main__":
    main()
