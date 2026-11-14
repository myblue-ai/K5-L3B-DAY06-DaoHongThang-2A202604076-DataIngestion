"""A: cắt cố định theo ký tự; B: gom theo đoạn văn. Chunk không vượt qua ranh giới trang."""
import re

from .models import Chunk, DocumentPage


def _chunk(page: DocumentPage, idx: int, text: str, start: int) -> Chunk:
    return Chunk(
        chunk_id=f"{page.document_id}:p{page.page}:c{idx}",   # ID ổn định -> nạp lại không trùng
        document_id=page.document_id, source=page.source, page=page.page, text=text,
        metadata={**page.metadata, "char_start": start},
    )


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    if not 0 <= overlap < size:
        raise ValueError("overlap phải >= 0 và < size")
    text, chunks, start = page.text, [], 0
    while start < len(text):
        piece = text[start:start + size]
        if piece.strip():
            chunks.append(_chunk(page, len(chunks), piece, start))
        if start + size >= len(text):
            break
        start += size - overlap                    # lùi lại `overlap` ký tự cho chunk sau
    return chunks


def _pack(units: list[str], max_size: int, sep: str) -> list[str]:
    """Gom các đơn vị liên tiếp vào chunk cho tới khi sắp vượt max_size."""
    out, buf = [], ""
    for u in units:
        if not buf:
            buf = u
        elif len(buf) + len(sep) + len(u) <= max_size:
            buf += sep + u
        else:
            out.append(buf)
            buf = u
    if buf:
        out.append(buf)
    return out


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    units = []
    for para in (p.strip() for p in page.text.split("\n\n")):
        if not para:
            continue
        if len(para) <= max_size:
            units.append(para)
            continue
        # Đoạn quá dài: tách theo câu, câu vẫn quá dài thì cắt cứng
        sentences = []
        for s in re.split(r"(?<=[.!?])\s+", para):
            sentences += [s[i:i + max_size] for i in range(0, len(s), max_size)]
        units += _pack(sentences, max_size, " ")
    chunks, cursor = [], 0
    for piece in _pack(units, max_size, "\n\n"):
        start = page.text.find(piece[:80], cursor)   # vị trí trong trang, dùng cho chấm coherence
        cursor = max(cursor, start)
        chunks.append(_chunk(page, len(chunks), piece, start))
    return chunks
