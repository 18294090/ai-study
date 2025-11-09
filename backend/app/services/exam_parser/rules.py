"""Regular expressions and rules for parsing."""

import re
from typing import List, Optional

from .core import LineBBox

# Question patterns
QUESTION_HEAD_RE = re.compile(r"^\s*(\d{1,4})[．\.、\)]\s*(.*)")
OPTION_RE = re.compile(r"^\s*([A-HＡ-Ｈ])[\.|、．\)]\s*(.+)")
MATERIAL_START_RE = re.compile(r"^\s*(?:材料[：:，,]|阅读(?:以下)?(?:材料|短文|文章|信息|资料))")
MULTI_CHOICE_HINT_RE = re.compile(r"多选|\(多选\)|【多选】|\[多选\]", re.I)
JUDGMENT_HINT_RE = re.compile(r"判断题|对错|是非|正确|错误", re.I)
FIGURE_LABEL_RE = re.compile(r"第\s*(\d{1,4})\s*题图")
OPTION_FIGURE_RE = re.compile(r"选项\s*([A-H])\s*图")
MATERIAL_RANGE_RE = re.compile(r"阅读.*?材料.*?第\s*(\d{1,4})\s*(?:-|—|－|至|到|~|～)\s*(\d{1,4})\s*题")
MATERIAL_RANGE_ONLY_RE = re.compile(r"回答第\s*(\d{1,4})\s*(?:-|—|－|至|到|~|～)\s*(\d{1,4})\s*题")
SECTION_HEADER_RE = re.compile(r"^[\s　]*[（(]?[一二三四五六七八九十]+[）)]?[、．\.]\s*(.+?题)")
TYPE_RANGE_RE = re.compile(r"第\s*(\d{1,4})\s*(?:-|—|－|至|到|~|～)\s*(\d{1,4})\s*题.*?(单选题|多选题|判断题|填空题|选择题|主观题)")
SECTION_COUNT_RE = re.compile(r"本大题共\s*(\d{1,4})\s*小题")
FIGURE_REF_TEXT_RE = re.compile(
    r"如图所示|如图|见图|见右图|见左图|下图|上图|右图|左图|示意图|流程图|图[一二三四五六七八九十]+|图\s*\(?\d+\)?|第\s*\d+\s*题图|如图[甲乙丙丁]|图[甲乙丙丁]",
    re.I,
)
FIGURE_TOKEN_RE = re.compile(
    r"图[：:．。.、]?\s*[（(]?[0-9０-９A-Za-z一二三四五六七八九十百千万甲乙丙丁-]+[)）]?",
    re.I,
)

# Section type mapping
SECTION_TYPE_MAP = {
    "选择题": "单选题",
    "多选题": "多选题",
    "单选题": "单选题",
    "判断题": "判断题",
    "填空题": "填空题",
    "简答题": "主观题",
    "问答题": "主观题",
    "论述题": "主观题",
}

FULLWIDTH_DIGIT_MAP = str.maketrans("０１２３４５６７８９", "0123456789")
CHINESE_NUM_MAP = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
CHINESE_UNIT_MAP = {"十": 10, "百": 100, "千": 1000, "万": 10000}


def _chinese_numeral_to_int(text: str) -> Optional[int]:
    if not text:
        return None
    result = 0
    current = 0
    unit = 1
    for ch in text:
        if ch in CHINESE_UNIT_MAP:
            unit_value = CHINESE_UNIT_MAP[ch]
            if current == 0:
                current = 1
            result += current * unit_value
            current = 0
            unit = 1
        elif ch in CHINESE_NUM_MAP:
            current = CHINESE_NUM_MAP[ch]
        else:
            return None
    result += current * unit
    return result


def normalize_figure_token(token: str) -> Optional[str]:
    token = re.sub(r"\s+", "", token)
    token = token.replace("：", "").replace(":", "")
    token = token.replace("．", "").replace("。", "").replace("、", "")
    if "图" not in token:
        return None
    token = token[token.index("图"):]
    suffix = token[1:]
    suffix = suffix.strip("()（）")
    if not suffix:
        return "图"
    suffix = suffix.translate(FULLWIDTH_DIGIT_MAP)
    suffix_upper = suffix.upper()
    if suffix_upper.isdigit():
        return f"图{suffix_upper}"
    elif all(ch in CHINESE_NUM_MAP or ch in CHINESE_UNIT_MAP for ch in suffix_upper):
        num = _chinese_numeral_to_int(suffix_upper)
        if num is not None:
            return f"图{num}"
    elif suffix_upper in {"甲", "乙", "丙", "丁", "A", "B", "C", "D"}:
        return f"图{suffix_upper}"
    else:
        return None


def extract_figure_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    if not text:
        return tokens
    for match in FIGURE_TOKEN_RE.finditer(text):
        token = match.group(0)
        norm = normalize_figure_token(token)
        if norm:
            tokens.add(norm)
    return tokens


def collect_tokens_near_bbox(
    lines: List[LineBBox],
    y0: float,
    y1: float,
    pad: float = 160.0,
) -> set[str]:
    contexts: List[str] = []
    extended_top = y0 - pad
    extended_bottom = y1 + pad
    for txt, (_, ty0, _, ty1) in lines:
        if ty0 <= extended_bottom and ty1 >= extended_top:
            contexts.append(txt)
    if not contexts:
        return set()
    return extract_figure_tokens("".join(contexts))