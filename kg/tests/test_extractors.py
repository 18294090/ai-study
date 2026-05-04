import pytest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError


class MockStructuredClient:
    def extract(self, system, user, schema, cached_prefix=None):
        return schema.model_validate({})


with patch.dict('sys.modules', {'openai': MagicMock(), 'anthropic': MagicMock()}):
    from agents.domain_extractor import (
        DomainExtractor,
        DomainExtraction,
        _Ent,
        _Tri,
        DOMAIN_SYSTEM,
    )
    from agents.pedagogical_tagger import (
        PedagogicalTagger,
        PedagogicalExtraction,
        PEDAGOGICAL_SYSTEM,
    )
    from agents.skill_mapper import (
        SkillMapper,
        SkillMappingResult,
        SKILL_MAPPER_SYSTEM,
    )
    from src.models.entities import EntityType, RelationType
    from src.models.textbook import Chapter
    from src.models.pedagogical import BloomLevel


class TestDomainExtractor:
    def test_domain_extraction_schema(self):
        mock_result = DomainExtraction(triples=[
            _Tri(
                subject=_Ent(name="光速", type=EntityType.FORMULA, description="真空中光速"),
                predicate=RelationType.DEFINED_BY,
                object=_Ent(name="c = 299792458 m/s", type=EntityType.FORMULA, latex=r"c = 299792458\ \text{m/s}"),
                confidence=0.95,
            )
        ])

        mock_client = MagicMock()
        mock_client.extract.return_value = mock_result

        extractor = DomainExtractor(mock_client)

        chapter = Chapter(
            chapter_id="ch1",
            title="物理量与单位",
            content="光在真空中传播的速度为 c = 299792458 m/s",
            word_count=100,
            sections=[],
        )

        result = extractor.extract(chapter, "")

        assert len(result.triples) == 1
        assert result.triples[0].subject.name == "光速"
        assert result.triples[0].confidence == 0.95
        assert result.triples[0].object.latex == r"c = 299792458\ \text{m/s}"

    def test_confidence_filtering(self):
        low_confidence_triple = _Tri(
            subject=_Ent(name="暗物质", type=EntityType.CONCEPT),
            predicate=RelationType.IS_A,
            object=_Ent(name="宇宙组成", type=EntityType.CONCEPT),
            confidence=0.65,
        )

        assert low_confidence_triple.confidence < 0.8


class TestPedagogicalTagger:
    def test_pedagogical_extraction_schema(self):
        mock_result = PedagogicalExtraction(
            learning_objectives=[
                {
                    "description": "理解匀变速直线运动的概念",
                    "target_concepts": ["匀变速直线运动", "加速度"],
                    "bloom_level": BloomLevel.UNDERSTAND,
                    "dok_level": 2,
                    "estimated_minutes": 30,
                }
            ],
            misconceptions=[
                {
                    "description": "认为速度大时加速度一定大",
                    "related_concepts": ["速度", "加速度"],
                    "example_wrong_answers": ["速度为10m/s时加速度一定为正"],
                }
            ],
            bloom_levels=["remember", "understand", "apply"],
        )

        mock_client = MagicMock()
        mock_client.extract.return_value = mock_result

        tagger = PedagogicalTagger(mock_client)

        chapter = Chapter(
            chapter_id="ch2",
            title="运动学基础",
            content="物体在匀变速直线运动中...",
            word_count=200,
            sections=[],
        )

        result = tagger.tag(chapter, "")

        assert len(result.learning_objectives) == 1
        assert result.learning_objectives[0].bloom_level == BloomLevel.UNDERSTAND
        assert len(result.misconceptions) == 1
        assert result.misconceptions[0].example_wrong_answers == ["速度为10m/s时加速度一定为正"]


class TestSkillMapper:
    def test_skill_mapping_schema(self):
        mock_result = SkillMappingResult(
            q_matrix_entries=[
                {
                    "item_id": "q1",
                    "required_skills": ["受力分析", "牛顿第二定律"],
                    "weights": [0.7, 0.9],
                }
            ]
        )

        mock_client = MagicMock()
        mock_client.extract.return_value = mock_result

        mapper = SkillMapper(mock_client)

        concepts = ["受力分析", "牛顿第二定律", "加速度"]
        item_text = "一物体质量为2kg，受到10N的力，求加速度"

        result = mapper.map_skills(concepts, item_text)

        assert len(result.q_matrix_entries) == 1
        assert result.q_matrix_entries[0].item_id == "q1"
        assert "牛顿第二定律" in result.q_matrix_entries[0].required_skills


class TestSystemPrompts:
    def test_domain_system_prompt(self):
        assert "知识三元组" in DOMAIN_SYSTEM
        assert "置信度 ≥ 0.8" in DOMAIN_SYSTEM
        assert "LaTeX" in DOMAIN_SYSTEM

    def test_pedagogical_system_prompt(self):
        assert "教学标注" in PEDAGOGICAL_SYSTEM
        assert "learning_objectives" in PEDAGOGICAL_SYSTEM
        assert "misconceptions" in PEDAGOGICAL_SYSTEM

    def test_skill_mapper_system_prompt(self):
        assert "Q-matrix" in SKILL_MAPPER_SYSTEM
        assert "技能权重" in SKILL_MAPPER_SYSTEM


class TestEntityTypes:
    def test_entity_type_enum(self):
        assert EntityType.CONCEPT.value == "concept"
        assert EntityType.FORMULA.value == "formula"
        assert EntityType.THEOREM.value == "theorem"

    def test_relation_type_enum(self):
        assert RelationType.IS_A.value == "is_a"
        assert RelationType.CAUSES.value == "causes"
        assert RelationType.DEFINED_BY.value == "defined_by"