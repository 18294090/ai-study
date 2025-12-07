"""DOCX document parsing."""

import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, List, Optional, Tuple

try:
    import docx
except Exception:
    docx = None

from ..core import Question
from ..rules import QUESTION_HEAD_RE, FIGURE_LABEL_RE
from ..utils import ensure_dir, extract_title_from_text_lines, parse_text_to_questions, normalize_text


def iter_docx_body_elements(doc):
    """Iterate through document paragraphs and embedded images in document order."""
    if docx is None:
        return
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    events: List[Tuple[str, object]] = []
    body = doc.element.body
    for child in body.iterchildren():
        tag = child.tag.lower()
        if tag.endswith('p'):
            p = Paragraph(child, doc)
            text = p.text
            if text and text.strip():
                events.append(("text", text))
            for run in p.runs:
                inline_elems = run._r.xpath('.//*[local-name()="blip"]')
                for blip in inline_elems:
                    rId = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                    if not rId:
                        continue
                    part = doc.part.related_parts.get(rId)
                    if not part or not getattr(part, "blob", None):
                        continue
                    image_bytes = part.blob
                    ext = ""
                    partname = getattr(part, "partname", None)
                    if partname:
                        ext = os.path.splitext(str(partname))[-1].lower().lstrip(".")
                    if not ext:
                        content_type = getattr(part, "content_type", "")
                        ext = {
                            "image/png": "png",
                            "image/jpeg": "jpg",
                            "image/jpg": "jpg",
                            "image/gif": "gif",
                            "image/bmp": "bmp",
                            "image/tiff": "tiff",
                        }.get(str(content_type), "")
                    if not ext:
                        ext = "png"
                    events.append(("image-bytes", (image_bytes, ext)))
        elif tag.endswith('tbl'):
            table = Table(child, doc)
            cell_texts = []
            for row in table.rows:
                for cell in row.cells:
                    if cell.text and cell.text.strip():
                        cell_texts.append(cell.text)
            if cell_texts:
                events.append(("text", "\n".join(cell_texts)))
    return events


def parse_docx(
    filepath: str,
    img_dir: str,
) -> List[Question]:
    if docx is None:
        logging.warning("python-docx not installed, skipping DOCX parsing: %s", filepath)
        return []
    ensure_dir(img_dir)
    document = docx.Document(filepath)
    events = iter_docx_body_elements(document)
    if not events:
        return []
    all_questions: List[Question] = []
    active_material = ""
    section_type_ctx = ""
    pending_images: List[str] = []
    page_text_segments: List[str] = []
    image_by_qnum: dict[int, List[str]] = {}
    label_qnum_queue: List[int] = []

    for kind, payload in events:
        if kind == "text":
            page_text_segments.append(str(payload))
    # Extract title as source - prioritize first line
    full_text = "\n".join(page_text_segments)
    lines = full_text.splitlines()
    source_title = ""
    if lines and lines[0].strip():
        source_title = normalize_text(lines[0])
    if not source_title:
        source_title = extract_title_from_text_lines(lines) or filepath

    page_text_segments.clear()
    for kind, payload in events:
        if kind == "text":
            txt = str(payload)
            page_text_segments.append(txt)
            lines = txt.splitlines() or [txt]
            for line in lines:
                stripped = line.strip()
                if stripped and QUESTION_HEAD_RE.match(stripped):
                    label_qnum_queue.clear()
                for m in FIGURE_LABEL_RE.finditer(stripped):
                    try:
                        label_qnum_queue.append(int(m.group(1)))
                    except Exception:
                        logging.debug("Failed to parse figure label number: %s", m.group(0))
        elif kind == "image-bytes":
            image_bytes: Optional[bytes]
            ext = "png"
            if isinstance(payload, tuple) and len(payload) == 2:
                raw_bytes, raw_ext = payload
                if isinstance(raw_bytes, (bytes, bytearray)):
                    image_bytes = bytes(raw_bytes)
                else:
                    image_bytes = None
                if isinstance(raw_ext, str) and raw_ext:
                    ext_candidate = re.sub(r"[^a-z0-9]", "", raw_ext.lower())
                    if ext_candidate:
                        ext = ext_candidate
            elif isinstance(payload, (bytes, bytearray)):
                image_bytes = bytes(payload)
            else:
                image_bytes = None
            if image_bytes is None:
                logging.debug("Skipping non-byte image payload: %s", type(payload))
                continue
            name = f"docx_{uuid.uuid4().hex[:8]}.{ext}"
            out_path = os.path.join(img_dir, name)
            with open(out_path, 'wb') as f:
                f.write(image_bytes)
            if label_qnum_queue:
                qnum = label_qnum_queue.pop(0)
                image_by_qnum.setdefault(qnum, []).append(out_path)
            else:
                pending_images.append(out_path)

    full_text = "\n".join(page_text_segments)
    if full_text.strip():
        qs, active_material, section_type_ctx = parse_text_to_questions(
            full_text.splitlines(),
            source=source_title,
            image_attach_queue=[],
            active_material=active_material,
            current_section_type=section_type_ctx,
        )
        if image_by_qnum and qs:
            num2q = {q.题号: q for q in qs if q.题号 is not None}
            for num, imgs in image_by_qnum.items():
                if num in num2q:
                    num2q[num].配图.extend(imgs)
                elif qs:
                    qs[-1].配图.extend(imgs)
        if pending_images and qs:
            qs[-1].配图.extend(pending_images)
        all_questions.extend(qs)
    return all_questions