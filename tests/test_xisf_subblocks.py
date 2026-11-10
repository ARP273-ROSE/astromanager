"""XISF 1.0 revision 2 (October 2026): compressed blocks split into subblocks, incompressible subblocks stored as is.

PixInsight >= 1.9.6 writes every compressed XISF this way (4 MiB subblocks). Files are built here by an encoder that
is independent from the reader, following section 10.6 of the specification.
"""
from __future__ import annotations

import hashlib
import sys
import zlib
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modules import compression  # noqa: E402

compression.HAS_XISF_LIB = False  # exercise the built-in reader, not the PyPI library


def _read(path):
    return compression.XISFReader(str(path)).read_image()[0]

SUBBLOCK = 64 * 1024  # 4 MiB in PixInsight; smaller here to keep test images light


def _shuffle(data: bytes, n: int) -> bytes:
    a = np.frombuffer(data, np.uint8)
    return a.reshape(len(a) // n, n).T.tobytes()


def _compress(codec: str, data: bytes) -> bytes:
    if codec == "zlib":
        return zlib.compress(data, 6)
    if codec == "zstd":
        zstandard = pytest.importorskip("zstandard")
        return zstandard.ZstdCompressor(level=10).compress(data)
    lz4b = pytest.importorskip("lz4.block")
    if codec == "lz4hc":
        return lz4b.compress(data, mode="high_compression", compression=9, store_size=False)
    return lz4b.compress(data, store_size=False)


def write_rev2(path: Path, a: np.ndarray, algo: str, subblock: int = SUBBLOCK) -> list[tuple[int, int]]:
    raw = a.tobytes()
    item = a.dtype.itemsize
    codec = algo.split("+")[0]
    data = _shuffle(raw, item) if algo.endswith("+sh") else raw
    chunks, sb = [], []
    for i in range(0, len(data), subblock):
        p = data[i:i + subblock]
        z = _compress(codec, p)
        if len(z) >= len(p):
            z = p
        chunks.append(z)
        sb.append((len(z), len(p)))
    block = b"".join(chunks)
    comp = f"{algo}:{len(raw)}:{item}" if algo.endswith("+sh") else f"{algo}:{len(raw)}"
    fmt = {"<u2": "UInt16", "<f4": "Float32"}[a.dtype.str]
    bounds = ' bounds="0:1"' if fmt == "Float32" else ""
    pos = 8192
    xml = (f'<?xml version="1.0" encoding="UTF-8"?><xisf version="1.0" xmlns="http://www.pixinsight.com/xisf">'
           f'<Image geometry="{a.shape[1]}:{a.shape[0]}:1" sampleFormat="{fmt}"{bounds} '
           f'location="attachment:{pos}:{len(block)}" compression="{comp}" '
           f'subblocks="{":".join(f"{c},{u}" for c, u in sb)}" '
           f'checksum="sha1:{hashlib.sha1(block).hexdigest()}"/></xisf>').encode()
    with open(path, "wb") as f:
        f.write(b"XISF0100" + len(xml).to_bytes(4, "little") + b"\0" * 4 + xml)
        f.write(b"\0" * (pos - 16 - len(xml)) + block)
    return sb


def _image(dtype: str) -> np.ndarray:
    """Smooth background (compressible high bytes) + noise (incompressible low bytes), like a real sub."""
    rng = np.random.default_rng(7)
    ny, nx = 300, 400
    a = 1000 + 50 * np.sin(np.arange(nx) / 40.0)[None, :] + rng.normal(0, 400, (ny, nx))
    if dtype == "<f4":
        return (a / 65535).astype("<f4")
    return np.clip(a, 0, 65535).astype("<u2")


@pytest.mark.parametrize("algo", ["zlib+sh", "zstd+sh", "lz4hc+sh", "lz4+sh", "zlib", "zstd"])
@pytest.mark.parametrize("dtype", ["<u2", "<f4"])
def test_subblocks_read_bit_exact(tmp_path, algo, dtype):
    a = _image(dtype)
    p = tmp_path / "rev2.xisf"
    assert len(write_rev2(p, a, algo)) > 1
    assert np.array_equal(_read(p), a)


def test_uncompressed_subblocks_present(tmp_path):
    a = _image("<f4")
    p = tmp_path / "raw.xisf"
    sb = write_rev2(p, a, "zstd+sh")
    assert any(c == u for c, u in sb) and any(c < u for c, u in sb)
    assert np.array_equal(_read(p), a)


def test_single_block_unchanged(tmp_path):
    """Files without a subblocks attribute (N.I.N.A., ASIAIR, this writer) read as before."""
    a = _image("<u2")
    p = tmp_path / "mono.xisf"
    compression.XISFWriter(str(p), codec="zlib", level=6, shuffle=True).write_image(a, {})
    assert np.array_equal(_read(p), a)
