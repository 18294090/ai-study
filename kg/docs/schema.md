# 三层知识图谱 Schema

## Layer 1 — Domain KG（学科知识图谱）
实体类型：concept / formula / theorem / person / event / location / work / time / dataset
关系类型：is_a / part_of / causes / equivalent_to / generalizes / contradicts /
         applies_to / requires / before / after / similar_to / defined_by / example_of
属性：name, description, latex, sympy_ast, source_doc, confidence,
     textbook_anchor: {textbook_id, chapter_id, paragraph_offset},
     community_id (Leiden)
SKOS 标注（v2.1 新增）：
  skos:broader / skos:narrower  → 替代 is_a，获得传递性公理
  skos:related                  → 替代 similar_to，获得对称性约束
  skos:exactMatch               → Wikidata QID 强等价对齐
  skos:closeMatch               → 跨教材近似等价（不触发自动合并）
附加属性：skos_exact_match (wikidata_qid), skos_close_match, skos_broader, skos_related

## Layer 2 — Pedagogical KG（教学知识图谱）
实体：textbook / chapter / section / learning_objective / lesson / activity / assessment / misconception
       curriculum_standard_node（v2.1 新增）
       ★ textbook→chapter→section 章节层级骨干（借鉴两阶段模式），为学习路径规划提供章节粒度拓扑序
       ★ curriculum_standard_node：国家课标形式化节点，只读，一次性导入
         属性：standard_id / subject / grade_band / bloom_required / exam_scope / exam_weight
关系：textbook --contains--> chapter --contains--> section --contains--> learning_objective /
     concept --aligned_to--> curriculum_standard_node  # 强制字段，每个 concept 必须对齐
     concept --exam_scope--> {gaokao / zhongkao / 双减_excluded}
     teaches / prerequisite_of / assesses / addresses_misconception /
     estimated_minutes / bloom_level / dok_level

## Layer 3 — Cognitive Diagnostic KG
实体：skill / sub_skill / q_matrix_entry
关系：requires_skill / composed_of / mastery_threshold
用途：BKT/DKT 输入；IRT Q-matrix