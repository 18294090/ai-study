"""Parse PDF tool using MinerU."""

from typing import Dict, Any, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def parse_pdf_tool(file_path: str) -> Dict[str, Any]:
    """Parse PDF using MinerU and return markdown and images.

    Args:
        file_path: Path to the PDF file

    Returns:
        Dict with 'success', 'markdown', 'images', 'char_count', 'image_count'
    """
    try:
        from mineru import MagicPDF

        client = MagicPDF(device="cpu")
        pdf_bytes = Path(file_path).read_bytes()
        result = client.parse(pdf_bytes, parse_method="full")

        markdown = result.get("markdown", "")
        images_info = result.get("images", []) or []

        logger.info(f"Parsed PDF with {len(markdown)} chars, {len(images_info)} images")

        return {
            "success": True,
            "markdown": markdown,
            "images": images_info,
            "char_count": len(markdown),
            "image_count": len(images_info),
        }

    except ImportError:
        logger.error("MinerU not installed")
        return {"success": False, "error": "MinerU not installed", "markdown": "", "images": []}
    except Exception as e:
        logger.error(f"Failed to parse PDF: {e}")
        return {"success": False, "error": str(e), "markdown": "", "images": []}
