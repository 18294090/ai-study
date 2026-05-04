from typing import Protocol, List, Dict, Tuple, Optional
from collections import Counter
import hashlib

from src.models import Textbook, Chapter, Section


class TextbookParser(Protocol):
    name: str

    def parse(self, pdf_path: str) -> Textbook:
        ...


class MultiParserVote:
    def __init__(self, parsers: List[TextbookParser]):
        self.parsers = parsers

    def parse(self, pdf_path: str) -> Textbook:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.parsers)) as ex:
            results = list(ex.map(lambda p: p.parse(pdf_path), self.parsers))
        return self._vote(results)

    def _vote(self, results: List[Textbook]) -> Textbook:
        if not results:
            raise ValueError("No parser results to vote on")

        if len(results) == 1:
            return results[0]

        voted_chapters = self._vote_chapters(results)
        total_words = sum(ch.word_count for ch in voted_chapters)

        return Textbook(
            textbook_id=results[0].textbook_id,
            title=results[0].title,
            subject=results[0].subject,
            chapters=voted_chapters,
            total_words=total_words,
            edition=results[0].edition,
        )

    def _vote_chapters(self, results: List[Textbook]) -> List[Chapter]:
        all_chapters_by_key: Dict[str, List[Chapter]] = {}

        for result in results:
            for ch in result.chapters:
                key = self._chapter_key(ch)
                if key not in all_chapters_by_key:
                    all_chapters_by_key[key] = []
                all_chapters_by_key[key].append(ch)

        voted = []
        for key, chapters in all_chapters_by_key.items():
            voted.append(self._majority_chapter(chapters))

        voted.sort(key=lambda c: (c.page_start if c.page_start is not None else 0, c.title))
        return voted

    def _chapter_key(self, ch: Chapter) -> str:
        key_str = f"{ch.page_start}"
        return hashlib.md5(key_str.encode()).hexdigest()[:8]

    def _majority_chapter(self, chapters: List[Chapter]) -> Chapter:
        if len(chapters) == 1:
            return chapters[0]

        normalized_titles = [c.title.lower().strip() for c in chapters]
        title_votes = Counter(normalized_titles)
        majority_normalized = title_votes.most_common(1)[0][0]

        candidates = [
            c for c in chapters
            if c.title.lower().strip() == majority_normalized
        ]
        if not candidates:
            candidates = chapters

        best = max(candidates, key=lambda c: c.word_count)

        majority_original_title = best.title

        merged_sections: List[Section] = []
        for c in candidates:
            merged_sections.extend(c.sections)

        section_map: Dict[Tuple[Optional[int], str], List[Section]] = {}
        for sec in merged_sections:
            key = (sec.page_start, sec.title)
            if key not in section_map:
                section_map[key] = []
            section_map[key].append(sec)

        voted_sections = []
        for key, secs in section_map.items():
            best_sec = max(secs, key=lambda s: s.word_count)
            voted_sections.append(best_sec)

        voted_sections.sort(key=lambda s: (s.page_start if s.page_start is not None else 0, s.title))

        all_content = [c.content for c in candidates]
        merged_content = "\n\n".join(sorted(set(all_content), key=len, reverse=True))

        return Chapter(
            chapter_id=best.chapter_id,
            title=majority_original_title,
            level=best.level,
            parent_id=best.parent_id,
            sections=voted_sections,
            content=merged_content,
            word_count=sum(c.word_count for c in candidates),
            page_start=best.page_start,
            page_end=best.page_end,
        )