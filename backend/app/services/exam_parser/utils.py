"""Utility functions for exam parsing."""

import logging
import os
import re
from collections import Counter as _Counter
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple
try:
    import fitz
except Exception:
    fitz = None
from .core import Question, LineBBox
from .rules import (
    QUESTION_HEAD_RE,
    OPTION_RE,
    MATERIAL_START_RE,
    MULTI_CHOICE_HINT_RE,
    JUDGMENT_HINT_RE,
    FIGURE_LABEL_RE,
    MATERIAL_RANGE_RE,
    MATERIAL_RANGE_ONLY_RE,
    SECTION_HEADER_RE,
    TYPE_RANGE_RE,
    SECTION_COUNT_RE,
    SECTION_TYPE_MAP,
    FIGURE_REF_TEXT_RE,
    extract_figure_tokens,
)
def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)
def normalize_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s)
    return s.strip()
def tokenize(text: str) -> List[str]:
    # Simple tokenization: Chinese characters, consecutive English letters, numbers
    toks = re.findall(r"[\u4e00-\u9fa5]|[A-Za-z]+|\d+", text)
    return [t.lower() for t in toks if t.strip()]
def cosine_sim(c1: _Counter, c2: _Counter) -> float:
    if not c1 or not c2:
        return 0.0
    # Calculate dot product and norms
    keys = set(c1.keys()) | set(c2.keys())
    dot = sum(c1.get(k, 0) * c2.get(k, 0) for k in keys)
    n1 = sum(v * v for v in c1.values()) ** 0.5
    n2 = sum(v * v for v in c2.values()) ** 0.5
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)
def extract_title_from_text_lines(lines: List[str]) -> str:
    # Prefer lines containing "试题卷/试卷/试题"
    for ln in lines:
        if any(k in ln for k in ["试题卷", "试卷", "试题"]):
            return normalize_text(ln)
    # Otherwise, concatenate the first two or three non-empty lines
    non_empty = [normalize_text(ln) for ln in lines if ln.strip()]
    return " ".join(non_empty[:3]) if non_empty else ""

def detect_qtype(text: str, options: List[str]) -> str:
    t = text.strip()
    opt_txt = "\n".join(options)
    if MULTI_CHOICE_HINT_RE.search(t) or MULTI_CHOICE_HINT_RE.search(opt_txt):
        return "多选题"
    if JUDGMENT_HINT_RE.search(t) or re.search(r"^(对|错|√|×)$", opt_txt.strip(), re.M):
        return "判断题"
    if len(options) >= 3 and all(re.match(r"^[A-HＡ-Ｈ]", o.strip()) for o in options):
        return "单选题"
    # Heuristics for short answer/fill-in-the-blank, etc.
    if re.search(r"简答|简述|问答|论述|填空|解答|计算", t):
        return "主观题"
    return "未知"
def parse_text_to_questions(
    lines: Iterable[str],
    source: str,
    image_attach_queue: Optional[List[str]] = None,
    active_material: str = "",
    current_section_type: str = "",
    type_ranges: Optional[List[Tuple[int, int, str]]] = None,
) -> Tuple[List[Question], str, str]:
    questions: List[Question] = []
    current_q_lines: List[str] = []
    current_options: List[str] = []
    current_q_images: List[str] = []
    last_q: Optional[Question] = None
    material_buffer = active_material
    in_material_block = False
    material_range: Optional[Tuple[int, int]] = None
    type_ranges = type_ranges or []
    section_type = current_section_type
    current_q_number: Optional[int] = None
    has_started_question: bool = False
    pending_section_count: Optional[int] = None
    pending_section_type: Optional[str] = None
    pending_section_start: Optional[int] = None
    def flush_question() -> None:
        nonlocal current_q_lines, current_options, current_q_images, last_q, material_buffer, material_range
        if not current_q_lines and not current_options:
            return
        raw_content = "\n".join(current_q_lines + current_options)
        content = raw_content.strip("\n")
        qtype = "未知"
        if section_type:
            qtype = section_type
        if current_q_number is not None:
            for a, b, tname in type_ranges:
                if a <= current_q_number <= b:
                    qtype = tname
                    break
        attach_material = material_buffer
        if material_range is not None:
            if current_q_number is None or not (material_range[0] <= current_q_number <= material_range[1]):
                attach_material = ""
        if not has_started_question:
            current_q_lines = []
            current_options = []
            current_q_images = []
            return
        q = Question(
            内容=content,
            来源=source,
            题型=qtype,
            配图=list(current_q_images),
            材料=attach_material,
            题号=current_q_number,
        )
        questions.append(q)
        last_q = q
        current_q_lines = []
        current_options = []
        current_q_images = []
        if material_range is not None and current_q_number is not None and current_q_number >= material_range[1]:
            material_range = None
            material_buffer = ""
    pending_images = list(image_attach_queue or [])
    for idx, raw in enumerate(lines):
        line = raw.rstrip("\r\n")
        stripped = line.strip()
        if not stripped:
            if in_material_block:
                material_buffer = f"{material_buffer}\n" if material_buffer else ""
                continue
            if has_started_question:
                current_q_lines.append("")
                continue
            in_material_block = False
            continue
        range_m = MATERIAL_RANGE_RE.search(stripped)
        if range_m:
            try:
                start_n = int(range_m.group(1))
                end_n = int(range_m.group(2))
                if start_n > end_n:
                    start_n, end_n = end_n, start_n
                material_range = (start_n, end_n)
            except Exception:
                material_range = None
            material_buffer = line
            in_material_block = True
            continue
        if MATERIAL_START_RE.search(stripped):
            material_buffer = line
            in_material_block = True
            continue
        if in_material_block:
            if QUESTION_HEAD_RE.match(stripped):
                in_material_block = False
            else:
                material_buffer = f"{material_buffer}\n{line}" if material_buffer else line
                rng = MATERIAL_RANGE_ONLY_RE.search(stripped)
                if rng:
                    try:
                        start_n = int(rng.group(1))
                        end_n = int(rng.group(2))
                        if start_n > end_n:
                            start_n, end_n = end_n, start_n
                        material_range = (start_n, end_n)
                    except Exception:
                        pass
                continue
        sec = SECTION_HEADER_RE.match(stripped)
        if sec:
            head = sec.group(1)
            for key, v in SECTION_TYPE_MAP.items():
                if key in head:
                    section_type = v
                    break
            pending_section_count = None
            pending_section_type = section_type or None
            pending_section_start = None
            continue
        tr = TYPE_RANGE_RE.search(stripped)
        if tr:
            a, b = int(tr.group(1)), int(tr.group(2))
            if a > b:
                a, b = b, a
            tname = tr.group(3)
            for key, v in SECTION_TYPE_MAP.items():
                if key in tname:
                    tname = v
                    break
            type_ranges.append((a, b, tname))
            continue
        if section_type:
            cnt_m = SECTION_COUNT_RE.search(stripped)
            if cnt_m:
                try:
                    pending_section_count = int(cnt_m.group(1))
                except Exception:
                    pending_section_count = None
                continue

        m = QUESTION_HEAD_RE.match(stripped)
        if m:
            flush_question()
            try:
                current_q_number = int(m.group(1))
            except Exception:
                current_q_number = None
            has_started_question = True
            if pending_section_count and pending_section_type and current_q_number is not None and pending_section_start is None:
                pending_section_start = current_q_number
                start = pending_section_start
                end = start + pending_section_count - 1
                type_ranges.append((start, end, pending_section_type))
            content_after = m.group(2)
            to_append = content_after.lstrip() if content_after else stripped
            current_q_lines.append(to_append)
            if pending_images:
                current_q_images.extend(pending_images)
                pending_images.clear()
            continue
        mo = OPTION_RE.match(stripped)
        if mo:
            current_options.append(line)
            continue
        current_q_lines.append(line)
    flush_question()
    if pending_images and questions:
        questions[-1].配图.extend(pending_images)
        pending_images.clear()
    return questions, material_buffer, section_type
def get_paddle_ocr(lang: str = "ch") -> Optional[Any]:
    try:
        from paddleocr import PaddleOCR
        # Try to initialize with minimal settings to avoid dependency issues
        return PaddleOCR(use_angle_cls=True, lang=lang)
    except ImportError as e:
        print(e)
        logging.debug("PaddleOCR import failed: %s", e)
        return None
    except Exception as e:
        print(e)
        logging.debug("PaddleOCR initialization failed: %s", e)
        return None
def extract_paddle_ocr_entries(result: Any) -> List[Tuple[str, Tuple[float, float, float, float]]]:
    """Extract text entries and bounding boxes from PaddleOCR result."""
    entries: List[Tuple[str, Tuple[float, float, float, float]]] = []
    if result is None:
        return entries
    try:
        # Handle different PaddleOCR result formats
        if isinstance(result, list) and len(result) > 0:
            # Check if it's a nested list (typical PaddleOCR format)
            if isinstance(result[0], list) and len(result[0]) > 0:
                # Format: [[text, confidence, bbox], ...]
                for item in result[0]:
                    if isinstance(item, list) and len(item) >= 2:
                        text = str(item[0]) if item[0] is not None else ""
                        if len(item) >= 2 and isinstance(item[1], (list, tuple)) and len(item[1]) >= 4:
                            # bbox format: [x1, y1, x2, y2] or [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                            bbox = item[1]
                            if isinstance(bbox, list) and len(bbox) == 4:
                                if isinstance(bbox[0], (int, float)):
                                    # Format: [x1, y1, x2, y2]
                                    x1, y1, x2, y2 = bbox
                                elif isinstance(bbox[0], (list, tuple)) and len(bbox[0]) >= 2:
                                    # Format: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                                    x1 = min(p[0] for p in bbox if isinstance(p, (list, tuple)) and len(p) >= 2)
                                    y1 = min(p[1] for p in bbox if isinstance(p, (list, tuple)) and len(p) >= 2)
                                    x2 = max(p[0] for p in bbox if isinstance(p, (list, tuple)) and len(p) >= 2)
                                    y2 = max(p[1] for p in bbox if isinstance(p, (list, tuple)) and len(p) >= 2)
                                else:
                                    continue
                                entries.append((text, (float(x1), float(y1), float(x2), float(y2))))
            else:
                # Try alternative formats
                for item in result:
                    if isinstance(item, dict):
                        # Dict format: {"text": "...", "bbox": [...], "confidence": ...}
                        text = item.get("text", "")
                        bbox = item.get("bbox", [])
                        if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                            if isinstance(bbox[0], (int, float)):
                                x1, y1, x2, y2 = bbox[:4]
                            elif isinstance(bbox[0], (list, tuple)) and len(bbox[0]) >= 2:
                                x1 = min(p[0] for p in bbox if isinstance(p, (list, tuple)) and len(p) >= 2)
                                y1 = min(p[1] for p in bbox if isinstance(p, (list, tuple)) and len(p) >= 2)
                                x2 = max(p[0] for p in bbox if isinstance(p, (list, tuple)) and len(p) >= 2)
                                y2 = max(p[1] for p in bbox if isinstance(p, (list, tuple)) and len(p) >= 2)
                            else:
                                continue
                            entries.append((text, (float(x1), float(y1), float(x2), float(y2))))
    except Exception as e:
        logging.debug("Error extracting PaddleOCR entries: %s", e)
    return entries

def ocr_image_to_text(image_path: str, paddle_lang: str = "ch") -> Tuple[str, List[LineBBox]]:
    def _load_sidecar() -> Optional[Any]:
        candidates: List[Path] = []
        base = Path(image_path)
        candidates.append(base.with_name(f"{base.stem}_res.json"))
        candidates.append(base.parent / "output" / f"{base.stem}_res.json")
        candidates.append(Path("output") / f"{base.stem}_res.json")
        extra_dir = os.getenv("PADDLE_OCR_OUTPUT_DIR")
        if extra_dir:
            candidates.append(Path(extra_dir) / f"{base.stem}_res.json")
        for candidate in candidates:
            try:
                if candidate.exists():
                    with open(candidate, "r", encoding="utf-8") as fh:
                        import json
                        return json.load(fh)
            except Exception as exc:
                logging.debug("Failed to load PaddleOCR JSON %s: %s", candidate, exc)
        return None

    entries: List[LineBBox] = []
    result: Any = None
    ocr = get_paddle_ocr(paddle_lang)
    if ocr is not None:
        try:
            result = ocr.predict(image_path)
        except TypeError:
            try:
                result = ocr.ocr(image_path)
            except Exception as exc:
                logging.warning("PaddleOCR recognition failed: %s", exc)
                result = None
        except Exception as exc:
            logging.warning("PaddleOCR recognition failed: %s", exc)
            result = None
    else:
        logging.warning("PaddleOCR not installed, trying to load exported JSON: %s", image_path)

    if result is not None:
        entries = extract_paddle_ocr_entries(result)
        if not entries and ocr is not None and hasattr(ocr, "ocr"):
            try:
                legacy = ocr.ocr(image_path)
                entries = extract_paddle_ocr_entries(legacy)
            except Exception:
                pass

    if not entries:
        sidecar = _load_sidecar()
        if sidecar is not None:
            entries = extract_paddle_ocr_entries(sidecar)

    text = "\n".join(line for line, _ in entries) if entries else ""
    return text, entries


def detect_document_type(input_path: str, sample_pages: int = 5) -> str:
    """Detect document type: text PDF, scanned PDF, Word, or image."""
    if os.path.isdir(input_path):
        return "directory"
    ext = Path(input_path).suffix.lower()
    if ext == ".pdf":
        if fitz is None:
            logging.debug("PyMuPDF not installed, defaulting to text PDF: %s", input_path)
            return "pdf_text"
        try:
            with fitz.open(input_path) as doc:
                total_pages = len(doc)
                if total_pages == 0:
                    return "pdf_text"
                check_pages = min(total_pages, max(sample_pages, 1))
                text_chars = 0
                non_empty_pages = 0
                for page_index in range(check_pages):
                    page = doc.load_page(page_index)
                    text = str(page.get_text("text") or "").strip()
                    if text:
                        text_chars += len(text)
                        non_empty_pages += 1
                        if text_chars >= 200:
                            break
                if non_empty_pages == 0 or text_chars < 120:
                    return "pdf_scanned"
        except Exception as exc:
            logging.debug("Failed to detect PDF text, defaulting to text PDF: %s", exc)
            return "pdf_text"
        return "pdf_text"
    if ext == ".docx":
        return "docx"
    if ext in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
        return "image"
    return "unsupported"


def parse_path(
    input_path: str,
    img_dir: str,
    paddle_lang: str = "ch",
    layout_model: Optional[Any] = None,
) -> List[Question]:
    from .parsers import parse_pdf, parse_docx, parse_image

    results: List[Question] = []

    def _parse_file(file_path: str) -> List[Question]:
        doc_type = detect_document_type(file_path)
        if doc_type == "directory":
            logging.debug("Path is directory, handled at upper level: %s", file_path)
            return []
        if doc_type == "unsupported":
            logging.debug("Skipping unsupported file: %s", file_path)
            return []
        logging.info("Detected document type %s: %s", doc_type, file_path)
        if doc_type == "pdf_text":
            return parse_pdf(
                file_path,
                img_dir,
                layout_model=layout_model,
                paddle_lang=paddle_lang,
            )
        if doc_type == "pdf_scanned":
            return parse_pdf(
                file_path,
                img_dir,
                layout_model=layout_model,
                paddle_lang=paddle_lang,
                force_ocr=True,
            )
        if doc_type == "docx":
            return parse_docx(file_path, img_dir)
        if doc_type == "image":
            return parse_image(
                file_path,
                img_dir,
                paddle_lang=paddle_lang,
            )
        logging.warning("Unknown document type: %s", file_path)
        return []

    if os.path.isdir(input_path):
        for root, _, files in os.walk(input_path):
            for fn in sorted(files):
                fp = os.path.join(root, fn)
                if os.path.isdir(fp):
                    continue
                if Path(fp).suffix.lower() not in {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
                    continue
                results.extend(_parse_file(fp))
        return results

    return _parse_file(input_path)


def export_results(questions: List[Question], out_path: str, fmt: str = "csv", include_number: bool = False) -> None:
    ensure_dir(os.path.dirname(os.path.abspath(out_path)) or ".")
    if fmt == "csv":
        import csv
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            header = ["题目内容", "题目类型", "来源", "材料"]
            if include_number:
                header = ["题号"] + header
            writer.writerow(header)
            for q in questions:
                row = q.to_csv_row()
                if include_number:
                    row = [q.题号 if q.题号 is not None else ""] + row
                writer.writerow(row)
    elif fmt == "json":
        import json
        data = []
        for q in questions:
            d = q.to_dict()
            if include_number:
                d["题号"] = q.题号
            data.append(d)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    elif fmt == "jsonl":
        import json
        with open(out_path, "w", encoding="utf-8") as f:
            for q in questions:
                d = q.to_dict()
                if include_number:
                    d["题号"] = q.题号
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
    else:
        raise ValueError(f"Unsupported export format: {fmt}")