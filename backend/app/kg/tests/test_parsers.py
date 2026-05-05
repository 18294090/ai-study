import pytest
from src.parsers.mineru_parser import MinerUParser
from src.models import Textbook


class TestMinerUParser:
    def test_parser_creation(self):
        parser = MinerUParser(device="cpu")
        assert parser.name == "mineru"
        assert parser.device == "cpu"

    def test_parser_creation_cuda(self):
        parser = MinerUParser(device="cuda")
        assert parser.name == "mineru"
        assert parser.device == "cuda"