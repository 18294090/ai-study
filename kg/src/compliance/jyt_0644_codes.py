from typing import Optional

SUBJECT_CODES = {
    "01": "语文",
    "02": "数学",
    "03": "英语",
    "04": "道德与法治",
    "05": "历史",
    "06": "地理",
    "07": "物理",
    "08": "化学",
    "09": "生物学",
    "10": "科学",
    "11": "音乐",
    "12": "美术",
    "13": "体育与健康",
    "14": "信息技术",
    "15": "劳动",
    "16": "综合实践活动",
    "17": "历史与社会",
    "18": "科学实践",
    "19": "思想政治",
    "20": "生物学实验",
    "21": "物理实验",
    "22": "化学实验",
}

LEVEL_CODES = {
    "P1": "小学一年级",
    "P2": "小学二年级",
    "P3": "小学三年级",
    "P4": "小学四年级",
    "P5": "小学五年级",
    "P6": "小学六年级",
    "J1": "初中一年级",
    "J2": "初中二年级",
    "J3": "初中三年级",
    "S1": "高中一年级",
    "S2": "高中二年级",
    "S3": "高中三年级",
}

COGNITIVE_LEVELS = {
    "remember": "记忆",
    "understand": "理解",
    "apply": "应用",
    "analyze": "分析",
    "evaluate": "评价",
    "create": "创造",
}

INTERNAL_TO_JYT_CLASS = {
    "concept": "LearningPoint",
    "formula": "LearningPoint",
    "theorem": "LearningPoint",
    "dataset": "LearningPoint",
    "textbook": "EducationalMaterial",
    "chapter": "EducationalMaterial",
    "section": "EducationalMaterial",
    "Question": "Question",
    "learning_objective": "LearningActivity",
    "lesson": "LearningActivity",
    "activity": "LearningActivity",
    "curriculum_standard_node": "CurriculumRequirement",
}

JYT_CLASSES = {
    "LearningPoint",
    "EducationalMaterial",
    "Question",
    "LearningActivity",
    "CurriculumRequirement",
    "DisciplinaryKeyCompetency",
    "TeachingMaterial",
    "Assessment",
}

INTERNAL_TO_JYT_RELATION = {
    ("prerequisite_of", "forward"): "isPrerequisiteFor",
    ("prerequisite_of", "backward"): "isPrerequisiteFor",
    ("skos:broader", "forward"): "hasChild",
    ("skos:broader", "backward"): "hasChild",
    ("is_a", "forward"): "hasChild",
    ("is_a", "backward"): "hasChild",
    ("skos:related", "forward"): "isRelatedTo",
    ("similar_to", "forward"): "isRelatedTo",
    ("skos:exactMatch", "forward"): "isEquivalentTo",
    ("equivalent_to", "forward"): "isEquivalentTo",
    ("includes", "forward"): "includes",
    ("part_of", "forward"): "includes",
    ("part_of", "backward"): "includes",
    ("teaches", "forward"): "hasRelatedKnowledgePoint",
    ("assesses", "forward"): "hasRelatedQuestion",
    ("aligned_to", "forward"): "requiresKnowledgePoint",
    ("contains", "forward"): "hasSupplementaryEducationalMaterial",
}


def get_jyt_subject_code(subject_name: str) -> Optional[str]:
    for code, name in SUBJECT_CODES.items():
        if name == subject_name:
            return code
    return None


def get_jyt_level_code(level_name: str) -> Optional[str]:
    for code, name in LEVEL_CODES.items():
        if name == level_name:
            return code
    return None