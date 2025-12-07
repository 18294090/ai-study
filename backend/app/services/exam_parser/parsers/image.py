"""Image OCR parsing."""

import logging
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, List, Optional, Set, Tuple
try:
    from PIL import Image
except Exception:
    Image = None
from ..core import LineBBox, Question
from ..rules import FIGURE_LABEL_RE, FIGURE_REF_TEXT_RE, extract_figure_tokens, OPTION_FIGURE_RE, OPTION_RE
from ..utils import ensure_dir, normalize_text, ocr_image_to_text, parse_text_to_questions, extract_paddle_ocr_entries, extract_title_from_text_lines, get_paddle_ocr


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


def parse_image(
    filepath: str,
    img_dir: str,
    paddle_lang: str = "ch",
) -> List[Question]:
    ensure_dir(img_dir)
    src_path = Path(filepath)
    ext = src_path.suffix.lower() or ".jpg"
    out_name = f"img_{src_path.stem}_{uuid.uuid4().hex[:8]}{ext}"
    out_path = Path(img_dir) / out_name
    try:
        shutil.copy2(src_path, out_path)
    except Exception as exc:
        logging.warning("Failed to copy image, using original path: %s", exc)
        out_path = src_path

    raw_text, entries = ocr_image_to_text(filepath, paddle_lang=paddle_lang)

    # Extract title as source - prioritize first line
    lines = raw_text.splitlines()
    title = ""
    if lines and lines[0].strip():
        title = normalize_text(lines[0])
    if not title:
        title = extract_title_from_text_lines(lines) or filepath

    if not raw_text.strip() and not entries:
        q = Question(内容="(图片OCR为空)", 来源=title, 题型="未知", 配图=[str(out_path)], 材料="")
        return [q]

    entries_sorted = sorted(entries, key=lambda item: (item[1][1], item[1][0])) if entries else []
    line_texts = [text for text, _ in entries_sorted] if entries_sorted else raw_text.splitlines()

    # Data cleaning: remove header and footer
    if len(line_texts) > 2:
        cleaned_line_texts = line_texts[1:-1]
    else:
        cleaned_line_texts = line_texts

    # Then use cleaned_line_texts for parsing

    figure_markers: List[Tuple[int, Tuple[float, float, float, float], int]] = []
    option_markers: List[Tuple[str, Tuple[float, float, float, float], int]] = []
    for idx, (text_line, bbox) in enumerate(entries_sorted):
        match = FIGURE_LABEL_RE.search(text_line)
        if match:
            try:
                qn = int(match.group(1))
            except Exception:
                continue
            figure_markers.append((qn, bbox, idx))
        match = OPTION_FIGURE_RE.search(text_line)
        if match:
            option = match.group(1)
            option_markers.append((option, bbox, idx))

    figure_marker_indices = {idx for _, _, idx in figure_markers} | {idx for _, _, idx in option_markers}
    if entries_sorted:
        lines_for_parsing = [text for idx, (text, _) in enumerate(entries_sorted) if idx not in figure_marker_indices]
    else:
        lines_for_parsing = cleaned_line_texts

    figure_images: dict[int, List[str]] = {}
    option_images: dict[str, List[str]] = {}
    pil_image = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    if Image is not None:
        try:
            pil_image = Image.open(filepath)
            if pil_image.mode not in ("RGB", "RGBA"):
                pil_image = pil_image.convert("RGB")
            pil_image.load()
            image_width, image_height = pil_image.size
        except Exception as exc:
            logging.debug("Failed to load image for cropping: %s", exc)
            pil_image = None
            image_width = None
            image_height = None

    if pil_image is not None and image_width is not None and image_height is not None:
        for qn, bbox, idx in figure_markers:
            y_top = float(bbox[3]) + 6.0
            y_bottom = float(image_height)
            for j in range(idx + 1, len(entries_sorted)):
                next_bbox = entries_sorted[j][1]
                if next_bbox[1] > y_top + 8.0:
                    y_bottom = min(y_bottom, float(next_bbox[1]))
                    break
            crop_top = max(0, int(round(y_top - 8.0)))
            crop_bottom = min(image_height, int(round(y_bottom + 8.0)))
            if crop_bottom - crop_top < 12:
                continue
            crop_box = (0, crop_top, image_width, crop_bottom)
            fig_name = f"fig_{qn}_{uuid.uuid4().hex[:8]}{ext}"
            fig_path = Path(img_dir) / fig_name
            try:
                cropped = pil_image.crop(crop_box)
                cropped.save(fig_path)
                # Check for nearby option
                assigned_to_option = False
                crop_y_bottom = crop_bottom
                crop_x_left = 0
                crop_x_right = image_width
                for text, (tx0, ty0, tx1, ty1) in entries_sorted:
                    match = OPTION_RE.match(text)
                    if match:
                        option = match.group(1)
                        # Below: ty0 > crop_y_bottom and close
                        if ty0 > crop_y_bottom and ty0 - crop_y_bottom < 200:
                            option_images.setdefault(option, []).append(str(fig_path))
                            assigned_to_option = True
                            break
                        # Left: tx1 < crop_x_left and vertical overlap
                        if tx1 < crop_x_left and crop_x_left - tx1 < 200 and ty0 <= crop_y_bottom and ty1 >= crop_top:
                            option_images.setdefault(option, []).append(str(fig_path))
                            assigned_to_option = True
                            break
                if not assigned_to_option:
                    figure_images.setdefault(qn, []).append(str(fig_path))
            except Exception as exc:
                logging.debug("Failed to crop figure: %s", exc)
        for option, bbox, idx in option_markers:
            y_top = float(bbox[3]) + 6.0
            y_bottom = float(image_height)
            for j in range(idx + 1, len(entries_sorted)):
                next_bbox = entries_sorted[j][1]
                if next_bbox[1] > y_top + 8.0:
                    y_bottom = min(y_bottom, float(next_bbox[1]))
                    break
            crop_top = max(0, int(round(y_top - 8.0)))
            crop_bottom = min(image_height, int(round(y_bottom + 8.0)))
            if crop_bottom - crop_top < 12:
                continue
            crop_box = (0, crop_top, image_width, crop_bottom)
            fig_name = f"option_{option}_{uuid.uuid4().hex[:8]}{ext}"
            fig_path = Path(img_dir) / fig_name
            try:
                cropped = pil_image.crop(crop_box)
                cropped.save(fig_path)
                option_images.setdefault(option, []).append(str(fig_path))
            except Exception as exc:
                logging.debug("Failed to crop option figure: %s", exc)
    elif figure_markers:
        for qn, _, _ in figure_markers:
            figure_images.setdefault(qn, []).append(str(out_path))
    elif option_markers:
        for option, _, _ in option_markers:
            option_images.setdefault(option, []).append(str(out_path))

    if pil_image is not None:
        try:
            pil_image.close()
        except Exception:
            pass

    qs, _, _ = parse_text_to_questions(
        lines_for_parsing,
        source=title,
        image_attach_queue=[],
        active_material="",
    )

    # Embed option images into content and convert to HTML
    for q in qs:
        if not q.内容:
            continue
        lines = q.内容.split('\n')
        new_lines = []
        for line in lines:
            match = OPTION_RE.match(line)
            if match:
                option = match.group(1)
                option_text = match.group(2).strip()  # Get text after option letter
                if option in option_images and option_images[option]:
                    img_tag = f"<img src='{option_images[option][0]}'>"
                    new_lines.append(f"{option}.{img_tag} {option_text}")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        html_content = '<br>'.join(new_lines)
        # Add attached images
        for img in q.配图:
            html_content += f'<br><img src="{img}">'
        q.内容 = html_content
        # Also convert material to HTML if needed
        if q.材料:
            q.材料 = q.材料.replace('\n', '<br>')

    if not qs:
        fallback_text = normalize_text(raw_text)
        qs = [Question(内容=fallback_text or "(图片OCR为空)", 来源=title, 题型="未知", 配图=[str(out_path)], 材料="")]

    assigned = False
    num2q = {q.题号: q for q in qs if q.题号 is not None}
    for qn, paths in figure_images.items():
        target = num2q.get(qn)
        if target is None and qs:
            target = qs[-1]
        if target is None:
            continue
        for img_path in paths:
            if img_path not in target.配图:
                target.配图.append(img_path)
                assigned = True

    if not assigned:
        referenced_questions = [q for q in qs if FIGURE_REF_TEXT_RE.search(q.内容)]
        for q in referenced_questions:
            if str(out_path) not in q.配图:
                q.配图.append(str(out_path))
                assigned = True

    if not assigned and len(qs) == 1 and not qs[0].配图:
        qs[0].配图.append(str(out_path))

    return qs