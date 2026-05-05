# Evaluation Datasets

This directory contains evaluation datasets for LearnHub KG pipeline.

## kg_triples_sample.jsonl

Format: JSONL (one JSON per line)
```json
{"chapter_text": "...", "expected_triples": [{"subject": "...", "predicate": "...", "object": "..."}]}
```

- 20 sample entries covering math, science, computer science domains
- For CI validation: F1 >= 0.80 required to pass

## question_sample.jsonl

Format: JSONL
```json
{"question": "...", "topic": "...", "difficulty": "easy|medium|hard", "expected_skills": ["..."]}
```

- 10 sample entries for question generation evaluation

## dialog_sample.jsonl

Format: JSONL
```json
{"student_query": "...", "expected_tutor_response_type": "...", "topic": "..."}
```

- 5 sample entries for Tutor dialog evaluation

## Adding Real Data

When real annotated data is added:
1. Replace sample files with full datasets
2. Update CI workflow to use full dataset paths
3. Record dataset version in DVC
