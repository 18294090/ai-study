#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDF parsing utilities."""
from __future__ import annotations
import io
import logging
import math
import os
import re
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Set, cast
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None
try:
    from PIL import Image
except Exception:
    Image = None
try:
    import numpy as np
except Exception:
    np = None
try:
    from paddleocr import PPStructureV3 as PPStructure
except Exception:
    PPStructure = None
from ..core import LineBBox, Question
from ..rules import (
    QUESTION_HEAD_RE,
    FIGURE_LABEL_RE,
    FIGURE_REF_TEXT_RE,
    extract_figure_tokens,
    OPTION_FIGURE_RE,
    OPTION_RE,
)
from ..utils import (
    get_paddle_ocr,
    extract_paddle_ocr_entries,
    extract_title_from_text_lines,
    parse_text_to_questions,
    ensure_dir,
    normalize_text,
)
PAGE_RENDER_ZOOM = 2.0
_LAYOUT_MODEL_CACHE: Dict[Tuple[str, float], Any] = {}

def get_layout_model(model_name: Optional[str] = None, threshold: float = 0.5) -> Optional[Any]:
    if PPStructure is None:
        return None
    cache_key = ("pp_structure_v3", threshold)
    if cache_key not in _LAYOUT_MODEL_CACHE:
        try:
            # PP-StructureV3 is the default model in paddleocr
            _LAYOUT_MODEL_CACHE[cache_key] = PPStructure(table=False, ocr=False)
        except Exception as exc:
            logging.warning("PP-StructureV3 模型加载失败：%s", exc)
            return None
    return _LAYOUT_MODEL_CACHE.get(cache_key)

def order_page_lines(lines: List[LineBBox], layout_blocks: Optional[List[Dict[str, Any]]] = None) -> List[LineBBox]:
    if not lines:
        return []
    sorted_lines = sorted(lines, key=lambda item: (item[1][1], item[1][0]))
    if not layout_blocks:
        return sorted_lines
    allowed_types = {"text", "title", "list", "paragraph"}
    ordered: List[LineBBox] = []
    used: Set[int] = set()
    textual_blocks = []
    for block in layout_blocks:
        bbox = block.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        btype = str(block.get("type", "")).lower()
        if allowed_types and btype and btype not in allowed_types:
            continue
        textual_blocks.append(block)
    textual_blocks.sort(key=lambda blk: (blk["bbox"][1], blk["bbox"][0]))
    margin = 12.0
    for block in textual_blocks:
        bx0, by0, bx1, by1 = block["bbox"]
        candidate_indices: List[int] = []
        for idx, (_, bbox) in enumerate(sorted_lines):
            if idx in used:
                continue
            x0, y0, x1, y1 = bbox
            cx = (x0 + x1) / 2.0
            cy = (y0 + y1) / 2.0
            if (bx0 - margin) <= cx <= (bx1 + margin) and (by0 - margin) <= cy <= (by1 + margin):
                candidate_indices.append(idx)
        if not candidate_indices:
            continue
        candidate_indices.sort(key=lambda i: (sorted_lines[i][1][1], sorted_lines[i][1][0]))
        for idx in candidate_indices:
            ordered.append(sorted_lines[idx])
            used.add(idx)
    if len(used) != len(sorted_lines):
        leftovers = [sorted_lines[i] for i in range(len(sorted_lines)) if i not in used]
        leftovers.sort(key=lambda item: (item[1][1], item[1][0]))
        ordered.extend(leftovers)
    # TODO: append remaining lines
    remaining = [sorted_lines[i] for i in range(len(sorted_lines)) if i not in used]
    ordered.extend(remaining)
    ordered.sort(key=lambda item: (item[1][1], item[1][0]))
    return ordered


def _merge_bbox(base: Tuple[float, float, float, float], extra: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    x0, y0, x1, y1 = base
    ex0, ey0, ex1, ey1 = extra
    return (min(x0, ex0), min(y0, ey0), max(x1, ex1), max(y1, ey1))


def compute_question_regions(lines: List[LineBBox]) -> Dict[int, Tuple[float, float, float, float]]:
    regions: Dict[int, Tuple[float, float, float, float]] = {}
    current_q: Optional[int] = None
    for text, bbox in lines:
        stripped = text.strip()
        if not stripped:
            continue
        m = QUESTION_HEAD_RE.match(stripped)
        if m:
            try:
                current_q = int(m.group(1))
            except Exception:
                current_q = None
            if current_q is not None:
                x0, y0, x1, y1 = bbox
                regions[current_q] = (float(x0), float(y0), float(x1), float(y1))
            continue
        if current_q is None:
            continue
        x0, y0, x1, y1 = bbox
        typed_bbox = (float(x0), float(y0), float(x1), float(y1))
        prev = regions.get(current_q, typed_bbox)
        regions[current_q] = _merge_bbox(prev, typed_bbox)
    return regions


def assign_image_by_region(cx: float, cy: float, regions: Dict[int, Tuple[float, float, float, float]]) -> Optional[int]:
    if not regions:
        return None
    best_qn: Optional[int] = None
    best_score = float("inf")
    for qn, (x0, y0, x1, y1) in regions.items():
        inside_x = (x0 - 40.0) <= cx <= (x1 + 40.0)
        inside_y = (y0 - 80.0) <= cy <= (y1 + 80.0)
        if inside_x and inside_y:
            return qn
        dy = 0.0
        if cy < y0:
            dy = y0 - cy
        elif cy > y1:
            dy = cy - y1
        dx = 0.0
        if cx < x0:
            dx = x0 - cx
        elif cx > x1:
            dx = cx - x1
        score = dy * 1.2 + dx * 0.3
        if score < best_score:
            best_score = score
            best_qn = qn
    return best_qn if best_score < 260.0 else None
def _parse_pdf_doc(
    doc: Any,
    filepath: str,
    img_dir: str,
    layout_model: Optional[Any] = None,
    paddle_lang: str = "ch",
    force_ocr: bool = False,
) -> List[Question]:
    CAPTION_VPAD = 120.0
    per_page = []
    def _combine_bboxes(bboxes: Iterable[Tuple[float, float, float, float]]) -> Optional[Tuple[float, float, float, float]]:
        iterator = iter(bboxes)
        try:
            merged = next(iterator)
        except StopIteration:
            return None
        for bbox in iterator:
            merged = _merge_bbox(merged, bbox)
        return merged

    def _rect_distance(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
        ax0, ay0, ax1, ay1 = a
        bx0, by0, bx1, by1 = b
        dx = 0.0
        if ax1 < bx0:
            dx = bx0 - ax1
        elif bx1 < ax0:
            dx = ax0 - bx1
        dy = 0.0
        if ay1 < by0:
            dy = by0 - ay1
        elif by1 < ay0:
            dy = ay0 - by1
        if dx == 0.0 and dy == 0.0:
            return 0.0
        return math.hypot(dx, dy)

    def _match_marker(
        image_bbox: Tuple[float, float, float, float],
        markers: List[Tuple[int, Tuple[float, float, float, float]]],
        threshold: float,
    ) -> Optional[int]:
        if not markers:
            return None
        best_qn: Optional[int] = None
        best_dist = float("inf")
        for qn, marker_bbox in markers:
            dist = _rect_distance(image_bbox, marker_bbox)
            if dist < best_dist:
                best_dist = dist
                best_qn = qn
        if best_qn is not None and best_dist <= threshold:
            return best_qn
        return None

    # Global tracking for extracted images across all pages
    global_extracted_xrefs: Set[int] = set()
    global_xref_to_path: Dict[int, str] = {}
    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        raw = page.get_text("rawdict")
        blocks = raw.get("blocks", []) if isinstance(raw, dict) else []
        page_lines: List[LineBBox] = []
        line_entries_raw: List[Dict[str, Any]] = []
        image_blocks: List[Tuple[str, Tuple[float, float, float, float]]] = []
        extracted_xrefs: Set[int] = set()
        xref_to_path: Dict[int, str] = {}
        for b in blocks:
            if b.get("type") == 0:
                for line in b.get("lines", []):
                    spans = line.get("spans", []) if isinstance(line, dict) else []
                    texts = []
                    bbox = None
                    sizes: List[float] = []
                    for span in spans:
                        chars = span.get("chars", [])
                        text = "".join(c.get("c", "") for c in chars if isinstance(c, dict))
                        if text:
                            texts.append(text)
                        sbbox = span.get("bbox")
                        if isinstance(sbbox, (list, tuple)) and len(sbbox) == 4:
                            x0, y0, x1, y1 = sbbox
                            bbox = (float(x0), float(y0), float(x1), float(y1))
                        try:
                            span_size = float(span.get("size"))
                            if span_size > 0:
                                sizes.append(span_size)
                        except Exception:
                            continue
                    if texts and bbox is not None:
                        text_value = "".join(texts)
                        max_size = max(sizes) if sizes else 0.0
                        page_lines.append((text_value, bbox))
                        line_entries_raw.append({
                            "text": text_value,
                            "bbox": bbox,
                            "size": max_size,
                        })
            elif b.get("type") == 1:
                # Image block - just collect bbox, extraction happens later
                bbox = tuple(b.get("bbox", (0, 0, 0, 0)))  # type: ignore
                image_blocks.append(("placeholder", bbox))  # placeholder path, will be replaced later
        page_text_raw = cast(str, page.get_text("text") or "")
        layout_blocks_scaled: List[Dict[str, Any]] = []
        np_img = None
        scale = 1.0
        need_render_for_layout = layout_model is not None
        need_render_for_ocr = force_ocr or not page_lines
        if (need_render_for_layout or need_render_for_ocr) and Image is not None and fitz is not None:
            try:
                zoom = PAGE_RENDER_ZOOM
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
                img_bytes = pix.tobytes("png")
                pil_img = Image.open(io.BytesIO(img_bytes))
                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")
                pil_img.load()
                if np is not None:
                    np_img = np.array(pil_img)
                scale = 1.0 / zoom
                page_width_pixels = pix.width
            except Exception as exc:
                logging.debug("页面渲染失败：%s", exc)
                np_img = None
                page_width_pixels = 2000
        else:
            page_width_pixels = 2000
        if layout_model is not None and np_img is not None:
            try:
                # PP-StructureV3 expects PIL Image, not numpy array
                if Image is not None:
                    pil_img = Image.fromarray(np_img)
                    layout_result = layout_model(pil_img)
                else:
                    layout_result = []

                for block in layout_result:
                    # PP-StructureV3 returns dict with 'bbox' key
                    bbox = block.get("bbox")
                    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                        x1, y1, x2, y2 = bbox
                        layout_blocks_scaled.append(
                            {
                                "bbox": (
                                    float(x1) * scale,
                                    float(y1) * scale,
                                    float(x2) * scale,
                                    float(y2) * scale,
                                ),
                                "type": block.get("type", "text"),
                            }
                        )
            except Exception as exc:
                logging.debug("版面分析失败：%s", exc)
                layout_blocks_scaled = []
        if np_img is not None and (force_ocr or not page_lines):
            ocr = get_paddle_ocr(paddle_lang)
            if ocr is not None:
                try:
                    ocr_result = ocr.predict(np_img, cls=True)
                    entries = extract_paddle_ocr_entries(ocr_result)
                    if entries:
                        for text, bbox in entries:
                            page_lines.append((text, bbox))
                            line_entries_raw.append({
                                "text": text,
                                "bbox": bbox,
                                "size": 0.0,
                            })
                except Exception as exc:
                    logging.warning("PaddleOCR 识别失败，回退 PyMuPDF：%s", exc)
        ordered_lines = order_page_lines(page_lines, layout_blocks_scaled)
        ordered_entries: List[Dict[str, Any]] = []
        used_flags = [False] * len(line_entries_raw)
        for text, bbox in ordered_lines:
            matched = False
            for idx, entry in enumerate(line_entries_raw):
                if used_flags[idx]:
                    continue
                if entry["text"] == text and entry["bbox"] == bbox:
                    ordered_entries.append(entry)
                    used_flags[idx] = True
                    matched = True
                    break
            if not matched:
                ordered_entries.append({
                    "text": text,
                    "bbox": bbox,
                    "size": 0.0,
                })
        if len(ordered_entries) < len(line_entries_raw):
            for idx, entry in enumerate(line_entries_raw):
                if not used_flags[idx]:
                    ordered_entries.append(entry)
                    used_flags[idx] = True
        ordered_text_lines = [entry["text"] for entry in ordered_entries if entry["text"]]
        page_text_final = "\n".join(ordered_text_lines).strip()

        # Calculate dynamic threshold based on page size
        dynamic_threshold = int(120 * (page_width_pixels / 2000.0))  # base 120 at 2000px
        per_page.append(
            {
                "index": page_index,
                "line_entries": ordered_entries,
                "lines": ordered_lines,
                "images": image_blocks,
                "text": page_text_final if page_text_final else page_text_raw,
                "extracted_xrefs": extracted_xrefs,
                "xref_to_path": xref_to_path,
                "layout_blocks": layout_blocks_scaled,
                "dynamic_threshold": dynamic_threshold,
            }
        )
    header_counter: Counter[str] = Counter()
    footer_counter: Counter[str] = Counter()
    HEADER_SAMPLE = 3
    FOOTER_SAMPLE = 3
    for p in per_page:
        entries = cast(List[Dict[str, Any]], p.get("line_entries", []))
        if not entries:
            continue
        top_slice = entries[:HEADER_SAMPLE]
        bottom_slice = entries[-FOOTER_SAMPLE:] if len(entries) >= FOOTER_SAMPLE else entries
        for entry in top_slice:
            norm = normalize_text(entry["text"])
            if norm:
                header_counter[norm] += 1
        for entry in bottom_slice:
            norm = normalize_text(entry["text"])
            if norm:
                footer_counter[norm] += 1
    MIN_REPEAT = 2
    header_texts = {text for text, count in header_counter.items() if count >= MIN_REPEAT}
    footer_texts = {text for text, count in footer_counter.items() if count >= MIN_REPEAT}
    for p in per_page:
        entries = cast(List[Dict[str, Any]], p.get("line_entries", []))
        if not entries:
            p["lines"] = []
            p["text"] = ""
            p["question_regions"] = {}
            p["figure_markers"] = []
            p["option_markers"] = []
            continue
        clean_entries: List[Dict[str, Any]] = []
        total = len(entries)
        for idx, entry in enumerate(entries):
            text_val = entry.get("text", "")
            if not text_val.strip():
                clean_entries.append(entry)
                continue
            norm = normalize_text(text_val)
            if idx < HEADER_SAMPLE and norm in header_texts:
                continue
            if (total - idx) <= FOOTER_SAMPLE and norm in footer_texts:
                continue
            clean_entries.append(entry)
        if not clean_entries:
            clean_entries = entries
        p["line_entries"] = clean_entries
        p["lines"] = [(entry["text"], entry["bbox"]) for entry in clean_entries]
        text_lines = [entry["text"] for entry in clean_entries]
        p["text"] = "\n".join(text_lines)
        p["question_regions"] = compute_question_regions(p["lines"])
        figure_markers: List[Tuple[int, Tuple[float, float, float, float]]] = []
        option_markers: List[Tuple[str, Tuple[float, float, float, float]]] = []
        for entry in clean_entries:
            txt = entry.get("text", "")
            bbox = cast(Tuple[float, float, float, float], entry.get("bbox", (0.0, 0.0, 0.0, 0.0)))
            match_fig = FIGURE_LABEL_RE.search(txt)
            if match_fig:
                try:
                    qn = int(match_fig.group(1))
                    figure_markers.append((qn, bbox))
                except Exception:
                    pass
            match_opt = OPTION_FIGURE_RE.search(txt)
            if match_opt:
                option_key = match_opt.group(1)
                option_markers.append((option_key, bbox))
        p["figure_markers"] = figure_markers
        p["option_markers"] = option_markers
    source_title = ""
    if per_page:
        first_entries = cast(List[Dict[str, Any]], per_page[0].get("line_entries", []))
        title_candidates: List[Tuple[float, str]] = []
        for entry in first_entries[:10]:
            text_val = normalize_text(entry.get("text", ""))
            if not text_val:
                continue
            size_val = 0.0
            try:
                size_val = float(entry.get("size", 0.0) or 0.0)
            except Exception:
                size_val = 0.0
            title_candidates.append((size_val, text_val))
        if title_candidates:
            max_size = max(size for size, _ in title_candidates)
            prominent = [text for size, text in title_candidates if size >= max_size - 1.0]
            prioritized = next((t for t in prominent if any(key in t for key in ["试题卷", "试卷", "试题"])), None)
            source_title = prioritized or prominent[0]
    if not source_title:
        try:
            page0_text = cast(str, doc.load_page(0).get_text("text") or "")
            fallback = extract_title_from_text_lines(page0_text.splitlines())
            if fallback:
                source_title = fallback
        except Exception:
            source_title = ""
    if not source_title:
        source_title = normalize_text(Path(filepath).stem) or Path(filepath).name
    active_material = ""
    section_type_ctx = ""
    all_lines_concat: List[str] = []
    for p in per_page:
        text_lines = p["text"].splitlines()
        if text_lines:
            all_lines_concat.extend(text_lines)
        else:
            all_lines_concat.extend([t for (t, _) in p["lines"]])
        all_lines_concat.append("")
    all_questions, active_material, section_type_ctx = parse_text_to_questions(
        all_lines_concat,
        source=source_title,
        image_attach_queue=[],
        active_material=active_material,
        current_section_type=section_type_ctx,
    )
    used_qnums: Set[int] = {int(q.题号) for q in all_questions if q.题号 is not None}
    for q in all_questions:
        if q.题号 is not None:
            continue
        head_match = QUESTION_HEAD_RE.match((q.内容 or "").strip())
        if head_match:
            try:
                inferred_qn = int(head_match.group(1))
            except Exception:
                inferred_qn = None
            else:
                if inferred_qn not in used_qnums:
                    q.题号 = inferred_qn
                    used_qnums.add(inferred_qn)
                    continue
        inferred_qn = None
        candidate = 1
        while candidate in used_qnums:
            candidate += 1
        inferred_qn = candidate
        q.题号 = inferred_qn
        used_qnums.add(inferred_qn)
    num2q = {q.题号: q for q in all_questions if q.题号 is not None}
    figure_tokens_by_qnum: dict[int, Set[str]] = {}
    for qn, q in num2q.items():
        q_tokens = extract_figure_tokens(q.内容)
        if q.材料:
            q_tokens.update(extract_figure_tokens(q.材料))
        figure_tokens_by_qnum[qn] = q_tokens
    option_images: dict[str, List[str]] = {}
    for p in per_page:
        page_lines: List[LineBBox] = cast(List[LineBBox], p["lines"])
        page_text_lines = p["text"].splitlines() if p["text"].strip() else [t for (t, _) in page_lines]
        figure_markers: List[Tuple[int, Tuple[float, float, float, float]]] = cast(
            List[Tuple[int, Tuple[float, float, float, float]]],
            p.get("figure_markers", []),
        )
        question_regions: Dict[int, Tuple[float, float, float, float]] = cast(
            Dict[int, Tuple[float, float, float, float]],
            p.get("question_regions", {}),
        )
        dynamic_threshold = cast(int, p.get("dynamic_threshold", 160))
        page_qnums: List[int] = []
        for ln in page_text_lines:
            m = QUESTION_HEAD_RE.match(ln)
            if m:
                try:
                    page_qnums.append(int(m.group(1)))
                except Exception:
                    pass
        anchor_by_qnum: dict[int, float] = {}
        for txt, bbox in page_lines:
            head = QUESTION_HEAD_RE.match(txt.strip())
            if not head:
                continue
            try:
                qn = int(head.group(1))
            except Exception:
                continue
            if qn not in num2q:
                continue
            y0, y1 = bbox[1], bbox[3]
            anchor_by_qnum[qn] = (float(y0) + float(y1)) / 2.0
        sorted_anchors = sorted(anchor_by_qnum.items(), key=lambda kv: kv[1])

        # Extract and assign remaining images that weren't processed above
        page_obj = None
        try:
            page_obj = doc.load_page(p["index"])
            imgs = page_obj.get_images(full=True)
        except Exception:
            imgs = []
        extracted_xrefs: Set[int] = p.get("extracted_xrefs", set())
        xref_to_path: Dict[int, str] = p.get("xref_to_path", {})

        for img_info in imgs:
            try:
                xref = int(img_info[0])
            except Exception:
                continue
            if xref in extracted_xrefs:
                continue
            bbox_list: List[Tuple[float, float, float, float]] = []
            try:
                if page_obj is not None and hasattr(page_obj, "get_image_rects"):
                    rects = page_obj.get_image_rects(xref)
                    for r in rects or []:
                        try:
                            bbox_list.append((float(r.x0), float(r.y0), float(r.x1), float(r.y1)))
                        except Exception:
                            continue
            except Exception:
                bbox_list = []

            if xref not in extracted_xrefs:
                try:
                    img = doc.extract_image(xref)
                    ext = img.get("ext", "png")
                    name = f"pdf_{p['index']+1}_{xref}_{uuid.uuid4().hex[:8]}.{ext}"
                    out_path = os.path.join(img_dir, name)
                    with open(out_path, "wb") as f:
                        f.write(img["image"])
                    extracted_xrefs.add(xref)
                    xref_to_path[xref] = out_path
                except Exception:
                    continue

            path = xref_to_path.get(xref)
            if not path:
                continue

            merged_bbox = _combine_bboxes(bbox_list)
            cx = cy = None
            if merged_bbox is not None:
                cx = (merged_bbox[0] + merged_bbox[2]) / 2.0
                cy = (merged_bbox[1] + merged_bbox[3]) / 2.0

            assigned = False
            if merged_bbox is not None:
                marker_threshold = max(float(dynamic_threshold) * 1.2, 200.0)
                marker_qn = _match_marker(merged_bbox, figure_markers, marker_threshold)
                if marker_qn is not None and marker_qn in num2q:
                    num2q[marker_qn].配图.append(path)
                    assigned = True

            if not assigned and merged_bbox is not None and cx is not None and cy is not None:
                region_qn = assign_image_by_region(cx, cy, question_regions)
                if region_qn is not None and region_qn in num2q:
                    num2q[region_qn].配图.append(path)
                    assigned = True

            if not assigned and sorted_anchors and cy is not None:
                target_qn: Optional[int] = None
                if cy <= sorted_anchors[0][1]:
                    target_qn = sorted_anchors[0][0]
                elif cy >= sorted_anchors[-1][1]:
                    target_qn = sorted_anchors[-1][0]
                else:
                    for (left_qn, left_y), (right_qn, right_y) in zip(sorted_anchors, sorted_anchors[1:]):
                        if left_y <= cy <= right_y:
                            # pick closer anchor
                            if abs(cy - left_y) <= abs(cy - right_y):
                                target_qn = left_qn
                            else:
                                target_qn = right_qn
                            break
                if target_qn is not None and target_qn in num2q:
                    num2q[target_qn].配图.append(path)
                    assigned = True

            if not assigned:
                logging.warning(
                    "未能匹配题号的图片：page=%s xref=%s path=%s",
                    p["index"] + 1,
                    xref,
                    path,
                )
    # Embed option images into content and convert to HTML
    for q in all_questions:
        if not q.内容:
            continue
        # Replace option images
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
            html_content += f"<br><img src='{img}'>"
        q.内容 = html_content
        # Also convert material to HTML if needed
        if q.材料:
            q.材料 = q.材料.replace('\n', '<br>')
    # heuristic to attach unmatched images to the last question
    return all_questions

def parse_pdf(
    filepath: str,
    img_dir: str,
    layout_model: Optional[Any] = None,
    paddle_lang: str = "ch",
    force_ocr: bool = False,
) -> List[Question]:
    if fitz is None:
        logging.warning("未安装 PyMuPDF，跳过 PDF 解析：%s", filepath)
        return []
    ensure_dir(img_dir)
    with fitz.open(filepath) as doc:        
        return _parse_pdf_doc(
            doc,
            filepath,
            img_dir,
            layout_model=layout_model,
            paddle_lang=paddle_lang,
            force_ocr=force_ocr,
        )