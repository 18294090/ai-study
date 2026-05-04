import pytest
from kg.src.models.entities import EntityType, RelationType, TextbookAnchor, EntityBase, Entity, JYTCompliantFields
from kg.src.models.triples import KnowledgeTriple
from kg.src.models.textbook import Section, Chapter, Textbook
from kg.src.models.pedagogical import BloomLevel, LearningObjective, Misconception, CurriculumStandardNode
from kg.src.models.diagnostic import Skill, QMatrixEntry


class TestThreeLayerEntities:
    def test_entity_base_fields(self):
        anchor = TextbookAnchor(textbook_id="t1", chapter_id="c1", paragraph_offset=5, page=42)
        entity_base = EntityBase(id="e1", name="Test Entity", anchor=anchor, confidence=0.9, layer="domain")
        assert entity_base.id == "e1"
        assert entity_base.name == "Test Entity"
        assert entity_base.anchor.textbook_id == "t1"
        assert entity_base.confidence == 0.9
        assert entity_base.layer == "domain"

    def test_domain_entity_with_formula_fields(self):
        entity = Entity(
            id="eq1",
            name="Quadratic Formula",
            type=EntityType.FORMULA,
            latex=r"x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}",
            sympy_ast='{"op": "Eq", "args": [...]}',
            community_id="comm_123",
            skos_broader="broader_concept_id",
            skos_related=["related1", "related2"],
            skos_exact_match="Q12345",
            skos_close_match="Q67890",
            curriculum_anchor="curriculum_node_1",
            exam_scope=["gaokao", "zhongkao"],
            description="The quadratic formula for solving ax^2 + bx + c = 0",
        )
        assert entity.type == EntityType.FORMULA
        assert entity.latex == r"x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}"
        assert entity.sympy_ast is not None
        assert entity.community_id == "comm_123"
        assert entity.skos_broader == "broader_concept_id"
        assert len(entity.skos_related) == 2
        assert "gaokao" in entity.exam_scope

    def test_pedagogical_learning_objective(self):
        lo = LearningObjective(
            id="lo1",
            name="Apply Quadratic Formula",
            description="Students can apply the quadratic formula to solve equations",
            target_concepts=["eq1", "eq2"],
            bloom_level=BloomLevel.APPLY,
            dok_level=3,
            estimated_minutes=30,
        )
        assert lo.layer == "pedagogical"
        assert lo.bloom_level == BloomLevel.APPLY
        assert lo.dok_level == 3
        assert "eq1" in lo.target_concepts

    def test_pedagogical_misconception(self):
        misconception = Misconception(
            id="mis1",
            name="Sign Error in Quadratic",
            description="Students often forget the negative sign before b",
            related_concepts=["eq1"],
            example_wrong_answers=[r"x = \frac{b \pm \sqrt{b^2-4ac}}{2a}"],
        )
        assert misconception.layer == "pedagogical"
        assert len(misconception.example_wrong_answers) == 1

    def test_pedagogical_curriculum_standard_node(self):
        csn = CurriculumStandardNode(
            id="csn1",
            name="Quadratic Equations Standard",
            standard_id="GB-2022-Math-9-3-1",
            subject="math",
            grade_band="义教9",
            content_requirement="理解和掌握一元二次方程的求根公式",
            bloom_required=BloomLevel.UNDERSTAND,
            exam_scope=["gaokao"],
            exam_weight=0.15,
            wikidata_qid="Q12345",
        )
        assert csn.layer == "pedagogical"
        assert csn.standard_id == "GB-2022-Math-9-3-1"
        assert csn.exam_weight == 0.15

    def test_diagnostic_skill(self):
        skill = Skill(
            id="skill1",
            name="Solve Quadratic Equations",
            parent_skill="skill0",
            mastery_threshold=0.85,
        )
        assert skill.layer == "diagnostic"
        assert skill.parent_skill == "skill0"
        assert skill.mastery_threshold == 0.85

    def test_diagnostic_qmatrix_entry(self):
        qme = QMatrixEntry(
            item_id="q1",
            required_skills=["skill1", "skill2"],
            weights=[0.7, 0.3],
        )
        assert qme.item_id == "q1"
        assert len(qme.required_skills) == 2
        assert sum(qme.weights) == 1.0


class TestTextbookAnchor:
    def test_anchor_creation(self):
        anchor = TextbookAnchor(textbook_id="t1", chapter_id="c1", paragraph_offset=10, page=100)
        assert anchor.textbook_id == "t1"
        assert anchor.chapter_id == "c1"
        assert anchor.paragraph_offset == 10
        assert anchor.page == 100

    def test_anchor_optional_fields(self):
        anchor = TextbookAnchor(textbook_id="t1", chapter_id="c1")
        assert anchor.paragraph_offset == 0
        assert anchor.page is None


class TestKnowledgeTripleDedupKey:
    def test_dedup_key_generation(self):
        entity1 = Entity(id="e1", name="Quadratic Formula", type=EntityType.FORMULA)
        entity2 = Entity(id="e2", name="Discriminant", type=EntityType.CONCEPT)
        triple = KnowledgeTriple(
            subject=entity1,
            predicate=RelationType.GENERALIZES,
            object=entity2,
        )
        key = triple.dedup_key()
        assert key == ("Quadratic Formula", EntityType.FORMULA, RelationType.GENERALIZES, "Discriminant", EntityType.CONCEPT)

    def test_dedup_key_same_for_equivalent_triples(self):
        entity1 = Entity(id="e1", name="Concept A", type=EntityType.CONCEPT)
        entity2 = Entity(id="e2", name="Concept B", type=EntityType.CONCEPT)
        triple1 = KnowledgeTriple(subject=entity1, predicate=RelationType.IS_A, object=entity2)
        triple2 = KnowledgeTriple(subject=entity1, predicate=RelationType.IS_A, object=entity2)
        assert triple1.dedup_key() == triple2.dedup_key()


class TestFormulaFields:
    def test_latex_field(self):
        entity = Entity(
            id="f1",
            name="Euler's Identity",
            type=EntityType.FORMULA,
            latex=r"e^{i\pi} + 1 = 0",
        )
        assert r"e^{i\pi}" in entity.latex

    def test_sympy_ast_field(self):
        entity = Entity(
            id="f2",
            name="Simple Equation",
            type=EntityType.FORMULA,
            sympy_ast='{"type": "Symbol", "name": "x"}',
        )
        assert "Symbol" in entity.sympy_ast

    def test_jyt_compliant_fields(self):
        entity = Entity(
            id="f3",
            name="JYT Field Test",
            type=EntityType.FORMULA,
            jyt=JYTCompliantFields(jyt_code="JYT2022", jyt_category="core"),
        )
        assert entity.jyt.jyt_code == "JYT2022"
        assert entity.jyt.jyt_category == "core"


class TestTextbookHierarchy:
    def test_section_creation(self):
        section = Section(
            section_id="s1",
            title="Solving Quadratics",
            parent_chapter_id="c1",
            content="This section covers...",
            word_count=500,
            page_start=10,
            page_end=15,
        )
        assert section.section_id == "s1"
        assert section.word_count == 500

    def test_chapter_with_sections(self):
        section = Section(
            section_id="s1",
            title="Section 1",
            parent_chapter_id="c1",
            content="Content",
            word_count=100,
        )
        chapter = Chapter(
            chapter_id="c1",
            title="Chapter 1",
            level=1,
            sections=[section],
            content="Full chapter content",
            word_count=1000,
        )
        assert len(chapter.sections) == 1
        assert chapter.sections[0].title == "Section 1"

    def test_textbook_with_chapters(self):
        chapter = Chapter(
            chapter_id="c1",
            title="Chapter 1",
            content="Content",
            word_count=2000,
        )
        textbook = Textbook(
            textbook_id="t1",
            title="Mathematics Grade 9",
            subject="math",
            chapters=[chapter],
            total_words=50000,
            edition="2024",
        )
        assert len(textbook.chapters) == 1
        assert textbook.subject == "math"
        assert textbook.edition == "2024"
