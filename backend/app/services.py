from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from fastapi import HTTPException, UploadFile

from .database import UPLOAD_DIR


MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_EXTRACTED_BYTES = 100 * 1024 * 1024
MAX_FILES = 500


def clean_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    return value[:120] or "未命名页面"


def _safe_member_path(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise HTTPException(status_code=400, detail="ZIP 中包含不安全的文件路径")
    if any(not part or part == "." for part in path.parts):
        raise HTTPException(status_code=400, detail="ZIP 中包含无效的文件路径")
    return path


async def save_upload(upload: UploadFile, slug: str) -> tuple[str, str]:
    filename = upload.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in {".html", ".htm", ".zip"}:
        raise HTTPException(status_code=400, detail="只支持 HTML 或 ZIP 文件")

    temp_path: Path | None = None
    staging: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp_path = Path(temp.name)
            total = 0
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="上传文件不能超过 50MB")
                temp.write(chunk)

        # 先写入独立的暂存目录，全部成功后再原子切换到正式目录：
        # 替换文件时即使新文件校验失败（损坏 ZIP/路径穿越/超限），旧内容也不会丢失。
        target = UPLOAD_DIR / slug
        staging = UPLOAD_DIR / f".staging-{slug}"
        staging.mkdir(parents=True, exist_ok=True)

        if suffix in {".html", ".htm"}:
            shutil.copyfile(temp_path, staging / "index.html")
            source_type = "html"
        else:
            _extract_zip(temp_path, staging)
            source_type = "zip"

        if target.exists():
            shutil.rmtree(target)
        staging.rename(target)
        staging = None
        return source_type, str(target.relative_to(UPLOAD_DIR))
    finally:
        await upload.close()
        if temp_path:
            temp_path.unlink(missing_ok=True)
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)


def _extract_zip(source: Path, target: Path) -> None:
    try:
        archive = zipfile.ZipFile(source)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="ZIP 文件损坏或格式不正确") from exc

    with archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        if len(members) == 0 or len(members) > MAX_FILES:
            raise HTTPException(status_code=400, detail="ZIP 文件内容为空或文件数量超过限制")

        parsed: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
        total_size = 0
        for item in members:
            path = _safe_member_path(item.filename)
            # ZIP symlinks can escape the extraction directory after deployment.
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise HTTPException(status_code=400, detail="ZIP 不允许包含符号链接")
            total_size += item.file_size
            if total_size > MAX_EXTRACTED_BYTES:
                raise HTTPException(status_code=400, detail="ZIP 解压后的内容不能超过 100MB")
            parsed.append((item, path))

        names = {path.as_posix().lower() for _, path in parsed}
        prefix = PurePosixPath()
        if "index.html" not in names:
            top_levels = {path.parts[0] for _, path in parsed if path.parts}
            if len(top_levels) == 1:
                candidate = next(iter(top_levels))
                if f"{candidate}/index.html" in names:
                    prefix = PurePosixPath(candidate)
        if prefix == PurePosixPath() and "index.html" not in names:
            raise HTTPException(status_code=400, detail="ZIP 根目录中需要包含 index.html")

        written: set[str] = set()
        for item, path in parsed:
            relative = path.relative_to(prefix) if prefix != PurePosixPath() else path
            if not relative.parts:
                continue
            destination = (target / Path(*relative.parts)).resolve()
            if target.resolve() not in destination.parents:
                raise HTTPException(status_code=400, detail="ZIP 中包含不安全的文件路径")
            key = destination.relative_to(target.resolve()).as_posix().lower()
            if key in written:
                raise HTTPException(status_code=400, detail="ZIP 中包含重复文件")
            written.add(key)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as input_file, destination.open("wb") as output_file:
                shutil.copyfileobj(input_file, output_file, length=1024 * 1024)

