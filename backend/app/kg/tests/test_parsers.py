import pytest
from unittest.mock import Mock
from src.parsers.multi_parser import TextbookParser, MultiParserVote
from src.models import Textbook, Chapter, Section
from src.formula.latex_to_sympy import latex_to_ast

_antlr_version_ok = False
try:
    from sympy.parsing.latex import parse_latex
    import sympy as sp
    expr = parse_latex(r'x')
    _antlr_version_ok = True
except Exception:
    pass

requires_antlr4_11 = pytest.mark.skipif(
    not _antlr_version_ok,
    reason="LaTeX parsing requires antlr4-python3-runtime==4.11"
)


class TestTextbookParserProtocol:
    def test_parser_protocol(self):
        def dummy_parse(pdf_path: str) -> Textbook:
            return Textbook(
                textbook_id="test",
                title="Test Book",
                subject="math",
                chapters=[],
                total_words=0,
            )

        parser: TextbookParser = Mock()
        parser.name = "dummy"
        parser.parse = dummy_parse

        result = parser.parse("test.pdf")
        assert result.textbook_id == "test"
        assert parser.name == "dummy"


class TestMultiParserVote:
    def test_single_parser_returns_same(self):
        parser = Mock(spec=TextbookParser)
        parser.name = "mock"
        parser.parse.return_value = Textbook(
            textbook_id="t1",
            title="Book",
            subject="math",
            chapters=[
                Chapter(
                    chapter_id="ch1",
                    title="Chapter 1",
                    level=1,
                    sections=[],
                    content="Content here",
                    word_count=100,
                    page_start=1,
                    page_end=10,
                )
            ],
            total_words=100,
        )

        vote = MultiParserVote([parser])
        result = vote.parse("test.pdf")

        assert result.textbook_id == "t1"
        assert len(result.chapters) == 1
        parser.parse.assert_called_once_with("test.pdf")

    def test_majority_vote_chapter_title(self):
        parser1 = Mock(spec=TextbookParser)
        parser1.name = "p1"
        parser1.parse.return_value = Textbook(
            textbook_id="t1",
            title="Book",
            subject="math",
            chapters=[
                Chapter(
                    chapter_id="ch1",
                    title="Chapter 1",
                    level=1,
                    sections=[],
                    content="Content 1",
                    word_count=100,
                    page_start=1,
                    page_end=10,
                )
            ],
            total_words=100,
        )

        parser2 = Mock(spec=TextbookParser)
        parser2.name = "p2"
        parser2.parse.return_value = Textbook(
            textbook_id="t1",
            title="Book",
            subject="math",
            chapters=[
                Chapter(
                    chapter_id="ch2",
                    title="Chapter 1",
                    level=1,
                    sections=[],
                    content="Content 2",
                    word_count=200,
                    page_start=1,
                    page_end=12,
                )
            ],
            total_words=200,
        )

        parser3 = Mock(spec=TextbookParser)
        parser3.name = "p3"
        parser3.parse.return_value = Textbook(
            textbook_id="t1",
            title="Book",
            subject="math",
            chapters=[
                Chapter(
                    chapter_id="ch3",
                    title="Chapter One",
                    level=1,
                    sections=[],
                    content="Content 3",
                    word_count=150,
                    page_start=1,
                    page_end=11,
                )
            ],
            total_words=150,
        )

        vote = MultiParserVote([parser1, parser2, parser3])
        result = vote.parse("test.pdf")

        assert len(result.chapters) == 1
        assert result.chapters[0].title == "Chapter 1"
        assert result.chapters[0].word_count == 300

    def test_multiple_chapters_merged(self):
        parser1 = Mock(spec=TextbookParser)
        parser1.name = "p1"
        parser1.parse.return_value = Textbook(
            textbook_id="t1",
            title="Book",
            subject="math",
            chapters=[
                Chapter(
                    chapter_id="ch1",
                    title="Chapter 1",
                    level=1,
                    sections=[],
                    content="Content 1",
                    word_count=100,
                    page_start=1,
                    page_end=10,
                ),
                Chapter(
                    chapter_id="ch2",
                    title="Chapter 2",
                    level=1,
                    sections=[],
                    content="Content 2",
                    word_count=200,
                    page_start=11,
                    page_end=20,
                ),
            ],
            total_words=300,
        )

        parser2 = Mock(spec=TextbookParser)
        parser2.name = "p2"
        parser2.parse.return_value = Textbook(
            textbook_id="t1",
            title="Book",
            subject="math",
            chapters=[
                Chapter(
                    chapter_id="ch1b",
                    title="Chapter 1",
                    level=1,
                    sections=[],
                    content="Content 1b",
                    word_count=120,
                    page_start=1,
                    page_end=10,
                ),
                Chapter(
                    chapter_id="ch2b",
                    title="Chapter 2",
                    level=1,
                    sections=[],
                    content="Content 2b",
                    word_count=180,
                    page_start=11,
                    page_end=20,
                ),
            ],
            total_words=300,
        )

        vote = MultiParserVote([parser1, parser2])
        result = vote.parse("test.pdf")

        assert len(result.chapters) == 2
        ch1 = result.chapters[0]
        assert ch1.title == "Chapter 1"
        assert ch1.page_start == 1
        ch2 = result.chapters[1]
        assert ch2.title == "Chapter 2"
        assert ch2.page_start == 11


class TestLatexToSympy:
    @requires_antlr4_11
    def test_simple_expression(self):
        result = latex_to_ast(r"x + 1")
        assert result is not None
        assert "x" in result
        assert "Add" in result or "Integer" in result

    @requires_antlr4_11
    def test_fraction(self):
        result = latex_to_ast(r"\frac{a}{b}")
        assert result is not None
        assert "a" in result or "Rational" in result

    @requires_antlr4_11
    def test_power(self):
        result = latex_to_ast(r"x^{2}")
        assert result is not None
        assert "Pow" in result or "Integer" in result

    def test_invalid_latex(self):
        result = latex_to_ast(r"\invalid{command}")
        assert result is None

    def test_empty_string(self):
        result = latex_to_ast("")
        assert result is None

    @requires_antlr4_11
    def test_square_root(self):
        result = latex_to_ast(r"\sqrt{x}")
        assert result is not None
        assert "sqrt" in result.lower() or "Pow" in result