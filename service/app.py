"""HTTP-сервис: API для жюри (по X-API-Key) + веб-интерфейс.

Запуск: uvicorn service.app:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .jobs import JobStore

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_EXT = {".mov", ".mp4", ".avi", ".mkv", ".m4v"}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv(ROOT / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

API_KEY = os.getenv("API_KEY", "")
if not API_KEY or API_KEY == "change-me":
    raise RuntimeError("Задайте API_KEY в .env (см. .env.example)")

store = JobStore(os.getenv("DATA_DIR", str(ROOT / "data")))
app = FastAPI(title="Cash Desk Violation Detector", version="0.1.0")


def require_key(x_api_key: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_api_key.encode(), API_KEY.encode()):
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


async def _accept_upload(file: UploadFile) -> dict:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"неподдерживаемый формат {ext!r}, ожидается .mov")
    job_id, job_dir = store.new_job_dir()
    dst = job_dir / f"input{ext}"
    size = 0
    with open(dst, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                dst.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="файл слишком большой")
            out.write(chunk)
    if size == 0:
        raise HTTPException(status_code=400, detail="пустой файл")
    store.submit(job_id, dst)
    return {"job_id": job_id, "status": "processing"}


def _job_or_404(job_id: str) -> dict:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    job.pop("video", None)
    job.pop("submitted_at", None)
    return job


# --- API для жюри ---

@app.post("/api/v1/analyze", dependencies=[Depends(require_key)])
async def api_analyze(file: UploadFile):
    return await _accept_upload(file)


@app.get("/api/v1/jobs/{job_id}", dependencies=[Depends(require_key)])
def api_job(job_id: str):
    return _job_or_404(job_id)


# --- Веб-интерфейс (без ключа) ---

@app.post("/ui/analyze")
async def ui_analyze(file: UploadFile):
    return await _accept_upload(file)


@app.get("/ui/jobs/{job_id}")
def ui_job(job_id: str):
    return _job_or_404(job_id)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(ROOT / "service" / "static" / "index.html")
