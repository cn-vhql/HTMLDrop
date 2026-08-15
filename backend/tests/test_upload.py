"""Upload service & ZIP safety tests."""
from __future__ import annotations

import io
import zipfile

import pytest
from fastapi import HTTPException

import app.services as services
from app.services import save_upload


class FakeUpload:
    def __init__(self, filename: str, data: bytes):
        self.filename = filename
        self._data = data

    async def read(self, size: int = -1):
        chunk = self._data[:size]
        self._data = self._data[size:]
        return chunk

    async def close(self):
        pass


def make_zip(files: dict[str, bytes], symlink: str | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
        if symlink:
            info = zipfile.ZipInfo(symlink)
            info.external_attr = (0o120000 << 16)  # S_IFLNK
            zf.writestr(info, "target")
    return buf.getvalue()


async def do_upload(filename: str, data: bytes, monkeypatch, tmp_path):
    monkeypatch.setattr(services, "UPLOAD_DIR", tmp_path / "uploads")
    return await save_upload(FakeUpload(filename, data), "slugtest")


@pytest.mark.asyncio
class TestSaveUpload:
    async def test_html_upload(self, monkeypatch, tmp_path):
        source_type, storage = await do_upload("page.html", b"<h1>hi</h1>", monkeypatch, tmp_path)
        assert source_type == "html"
        assert storage == "slugtest"
        assert (tmp_path / "uploads" / "slugtest" / "index.html").read_text() == "<h1>hi</h1>"

    async def test_htm_extension(self, monkeypatch, tmp_path):
        source_type, _ = await do_upload("page.htm", b"<p>hi</p>", monkeypatch, tmp_path)
        assert source_type == "html"

    async def test_reject_bad_extension(self, monkeypatch, tmp_path):
        with pytest.raises(HTTPException) as exc:
            await do_upload("evil.exe", b"MZ", monkeypatch, tmp_path)
        assert exc.value.status_code == 400

    async def test_reject_oversize(self, monkeypatch, tmp_path):
        monkeypatch.setattr(services, "MAX_UPLOAD_BYTES", 100)
        with pytest.raises(HTTPException) as exc:
            await do_upload("big.html", b"x" * 200, monkeypatch, tmp_path)
        assert exc.value.status_code == 413

    async def test_zip_extract(self, monkeypatch, tmp_path):
        z = make_zip({"index.html": b"<h1>site</h1>", "assets/app.js": b"console.log(1)"})
        source_type, _ = await do_upload("site.zip", z, monkeypatch, tmp_path)
        assert source_type == "zip"
        assert (tmp_path / "uploads" / "slugtest" / "assets" / "app.js").read_text() == "console.log(1)"

    async def test_zip_missing_index(self, monkeypatch, tmp_path):
        z = make_zip({"readme.txt": b"hi"})
        with pytest.raises(HTTPException) as exc:
            await do_upload("bad.zip", z, monkeypatch, tmp_path)
        assert exc.value.status_code == 400

    async def test_zip_single_top_dir(self, monkeypatch, tmp_path):
        z = make_zip({"site/index.html": b"<h1>nested</h1>", "site/style.css": b"body{}"})
        source_type, _ = await do_upload("nested.zip", z, monkeypatch, tmp_path)
        assert source_type == "zip"
        assert (tmp_path / "uploads" / "slugtest" / "index.html").read_text() == "<h1>nested</h1>"
        assert (tmp_path / "uploads" / "slugtest" / "style.css").read_text() == "body{}"

    async def test_zip_multiple_roots_without_index_rejected(self, monkeypatch, tmp_path):
        z = make_zip({"a/index.html": b"x", "b/page.html": b"y"})
        with pytest.raises(HTTPException) as exc:
            await do_upload("multi.zip", z, monkeypatch, tmp_path)
        assert exc.value.status_code == 400

    async def test_zip_root_index_with_extra_dir_allowed(self, monkeypatch, tmp_path):
        z = make_zip({"index.html": b"ok", "other/page.html": b"x"})
        source_type, _ = await do_upload("ok.zip", z, monkeypatch, tmp_path)
        assert source_type == "zip"
        assert (tmp_path / "uploads" / "slugtest" / "other" / "page.html").read_text() == "x"

    async def test_zip_traversal_rejected(self, monkeypatch, tmp_path):
        z = make_zip({"../escape.txt": b"evil", "index.html": b"ok"})
        with pytest.raises(HTTPException) as exc:
            await do_upload("evil.zip", z, monkeypatch, tmp_path)
        assert exc.value.status_code == 400
        assert not (tmp_path.parent / "escape.txt").exists()

    async def test_zip_backslash_traversal_rejected(self, monkeypatch, tmp_path):
        z = make_zip({"..\\escape.txt": b"evil", "index.html": b"ok"})
        with pytest.raises(HTTPException):
            await do_upload("evil2.zip", z, monkeypatch, tmp_path)

    async def test_zip_symlink_rejected(self, monkeypatch, tmp_path):
        z = make_zip({"index.html": b"ok"}, symlink="link")
        with pytest.raises(HTTPException) as exc:
            await do_upload("link.zip", z, monkeypatch, tmp_path)
        assert exc.value.status_code == 400

    async def test_zip_too_many_files(self, monkeypatch, tmp_path):
        monkeypatch.setattr(services, "MAX_FILES", 3)
        z = make_zip({f"f{i}.txt": b"x" for i in range(5)} | {"index.html": b"ok"})
        with pytest.raises(HTTPException):
            await do_upload("many.zip", z, monkeypatch, tmp_path)

    async def test_zip_extract_size_limit(self, monkeypatch, tmp_path):
        monkeypatch.setattr(services, "MAX_EXTRACTED_BYTES", 50)
        z = make_zip({"index.html": b"x" * 100})
        with pytest.raises(HTTPException):
            await do_upload("fat.zip", z, monkeypatch, tmp_path)

    async def test_corrupt_zip(self, monkeypatch, tmp_path):
        with pytest.raises(HTTPException) as exc:
            await do_upload("bad.zip", b"not a zip at all", monkeypatch, tmp_path)
        assert exc.value.status_code == 400

    async def test_failed_replace_keeps_old_content(self, monkeypatch, tmp_path):
        monkeypatch.setattr(services, "UPLOAD_DIR", tmp_path / "uploads")
        good = make_zip({"index.html": b"<h1>v1</h1>"})
        await save_upload(FakeUpload("ok.zip", good), "keep")
        assert (tmp_path / "uploads" / "keep" / "index.html").read_text() == "<h1>v1</h1>"
        # 用损坏 ZIP 替换 -> 失败且旧内容保留
        with pytest.raises(HTTPException):
            await save_upload(FakeUpload("bad.zip", b"garbage"), "keep")
        assert (tmp_path / "uploads" / "keep" / "index.html").read_text() == "<h1>v1</h1>"
        assert not list((tmp_path / "uploads").glob(".staging-*"))


def test_clean_name():
    assert services.clean_name("  多  空格  ") == "多 空格"
    assert services.clean_name("x" * 300) == "x" * 120
    assert services.clean_name("   ") == "未命名页面"
