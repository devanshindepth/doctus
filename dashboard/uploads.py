"""Bounded temporary uploads, scanned in short-lived subprocesses."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()
ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = ROOT / "scratch" / "uploads"
MAX_BYTES = 20 * 1024 * 1024
slots = asyncio.Semaphore(2)


def matches_media(header: bytes, ext: str) -> bool:
    if ext in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if ext == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == ".webp":
        return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    return ext == ".mp4" and len(header) >= 12 and header[4:8] == b"ftyp"


async def scan_worker(path: Path, channel: str, territory: str) -> dict:
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "doctus.server.asset_scan", str(path), channel, territory,
        cwd=str(ROOT), env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        output, _ = await asyncio.wait_for(process.communicate(), 30)
        if process.returncode:
            raise HTTPException(422, "This file could not be scanned safely. Try an intact original.")
        return json.loads(output)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


@router.post("/api/assets/scan")
async def upload_and_scan(
    request: Request,
    filename: str = Query(..., min_length=1, max_length=255),
    channel: Literal["social", "festival", "trailer", "theatrical"] = "social",
    territory: Literal["US", "EU", "Global"] = "US",
):
    extension = Path(filename).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp", ".mp4"}:
        raise HTTPException(415, "Choose a JPG, PNG, WebP, or MP4 file.")
    if request.headers.get("content-type", "").split(";")[0] != "application/octet-stream":
        raise HTTPException(415, "Send the file as application/octet-stream.")
    try:
        length = int(request.headers.get("content-length", "0"))
    except ValueError:
        raise HTTPException(400, "Invalid upload size.")
    if length > MAX_BYTES:
        raise HTTPException(413, "This file is too large. The limit is 20 MB.")
    if slots.locked():
        raise HTTPException(429, "The scanner is busy. Try again shortly.", headers={"Retry-After": "5"})
    async with slots:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = None
        try:
            async with asyncio.timeout(60):
                with tempfile.NamedTemporaryFile(dir=UPLOAD_DIR, suffix=extension, delete=False) as target:
                    path = Path(target.name)
                    size = 0
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise HTTPException(413, "This file is too large. The limit is 20 MB.")
                        target.write(chunk)
                if not size:
                    raise HTTPException(400, "This file is empty. Choose another file.")
                with path.open("rb") as source:
                    if not matches_media(source.read(16), extension):
                        raise HTTPException(415, "File contents do not match its format. Choose an original media file.")
                result = await scan_worker(path, channel, territory)
                return {"ok": True, "data": {**result, "filename": Path(filename.replace("\\", "/")).name,
                                               "size_bytes": size}}
        except TimeoutError:
            raise HTTPException(408, "The scan timed out. Try a smaller file or scan again.")
        finally:
            if path is not None:
                path.unlink(missing_ok=True)
