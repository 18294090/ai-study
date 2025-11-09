"""Command line interface for exam parser."""

import argparse
import logging
import sys
import os

# Handle relative imports when run directly
if __name__ == "__main__" and __package__ is None:
    # Add parent directory to path for relative imports
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "exam_parser"

try:
    from .utils import parse_path, export_results
    from .parsers.pdf import get_layout_model
except ImportError:
    # Fallback for direct execution
    from utils import parse_path, export_results
    from parsers.pdf import get_layout_model


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="从PDF、DOCX和图像文件中提取试题，支持OCR和版面分析")
    p.add_argument("--input", "-i", required=True, help="输入文件或目录（支持：pdf、docx、图像）")
    p.add_argument("--out", "-o", default="output.csv", help="输出文件路径，默认为output.csv")
    p.add_argument("--img-dir", default="extracted_images", help="提取图像保存目录，默认为extracted_images")
    p.add_argument("--format", "-f", choices=["csv", "json", "jsonl"], default="csv", help="导出格式：csv、json或jsonl")
    p.add_argument("--log", default="INFO", help="日志级别：DEBUG/INFO/WARN/ERROR，默认为INFO")
    p.add_argument("--include-number", action="store_true", help="在导出中包含题号列")
    p.add_argument("--paddle-lang", default="ch", help="PaddleOCR语言代码，默认为ch")
    p.add_argument("--use-layout", action="store_true", help="启用PP-StructureV3版面分析")
    p.add_argument(
        "--layout-model",
        default="pp_structure_v3",
        help="PP-StructureV3版面分析模型（目前仅支持pp_structure_v3）",
    )
    p.add_argument(
        "--layout-threshold",
        type=float,
        default=0.5,
        help="版面检测置信度阈值（0~1），默认为0.5",
    )
    return p


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log.upper(), logging.INFO), format="%(levelname)s: %(message)s")

    layout_model = None
    if getattr(args, "use_layout", False):
        layout_model = get_layout_model(args.layout_model, threshold=args.layout_threshold)
        if layout_model is None:
            logging.warning("Layout analysis not enabled or model failed to load, using original order.")

    questions = parse_path(
        args.input,
        args.img_dir,
        paddle_lang=args.paddle_lang,
        layout_model=layout_model,
    )

    if not questions:
        logging.warning("No questions parsed.")
        sys.exit(1)
    export_results(questions, args.out, args.format, include_number=args.include_number)
    logging.info("Completed, exported %d questions: %s", len(questions), args.out)


if __name__ == "__main__":
    main()