import aiofiles
import shutil
from pathlib import Path
from datetime import datetime
import structlog

from config import settings

log = structlog.get_logger()


async def save_upload(file_content: bytes, filename: str, job_id: str) -> str:
    """Save uploaded file to NFS incoming directory. Returns the full path."""
    now = datetime.utcnow()
    dest_dir = Path(settings.NFS_INCOMING_PATH) / str(now.year) / f"{now.month:02d}" / job_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_path = dest_dir / filename
    async with aiofiles.open(str(dest_path), "wb") as f:
        await f.write(file_content)

    log.info("file_saved", path=str(dest_path), size=len(file_content))
    return str(dest_path)


async def move_to_processed(file_path: str, job_id: str) -> str:
    """Move a completed file to the processed directory."""
    src = Path(file_path)
    dest_dir = Path(settings.NFS_PROCESSED_PATH) / job_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name

    shutil.move(str(src), str(dest))
    log.info("file_moved_processed", src=str(src), dest=str(dest))
    return str(dest)


async def move_to_failed(file_path: str, job_id: str) -> str:
    """Move a failed file to the failed directory."""
    src = Path(file_path)
    dest_dir = Path(settings.NFS_FAILED_PATH) / job_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name

    shutil.move(str(src), str(dest))
    log.info("file_moved_failed", src=str(src), dest=str(dest))
    return str(dest)


async def archive_file(file_path: str, job_id: str) -> str:
    """Move file to archive directory (for deleted jobs)."""
    src = Path(file_path)
    if not src.exists():
        return ""

    dest_dir = Path(settings.NFS_ARCHIVE_PATH) / job_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name

    shutil.move(str(src), str(dest))
    log.info("file_archived", src=str(src), dest=str(dest))
    return str(dest)


def get_file_size(file_path: str) -> int:
    """Get file size in bytes."""
    return Path(file_path).stat().st_size


def check_nfs_writable() -> bool:
    """Health check: verify NFS mount is writable."""
    try:
        test_dir = Path(settings.NFS_BASE_PATH)
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / ".health_check"
        test_file.write_text("ok")
        test_file.unlink()
        return True
    except Exception:
        return False
