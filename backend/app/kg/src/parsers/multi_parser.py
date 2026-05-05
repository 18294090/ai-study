from typing import List
from ..models import Textbook, Chapter, Section

from .mineru_parser import MinerUParser


def create_parser(device: str = "cuda") -> MinerUParser:
    """Create MinerU parser for document parsing."""
    return MinerUParser(device=device)


def parse_textbook(pdf_path: str, device: str = "cuda") -> Textbook:
    """Parse a textbook PDF using MinerU parser."""
    parser = create_parser(device)
    return parser.parse(pdf_path)