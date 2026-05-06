# Exam Extraction Skill

## Purpose
Extract structured questions from exam PDFs using MinerU parsing and LLM extraction.

## Tools
- `parse_pdf_tool`: Parse PDF using MinerU → markdown + images
- `extract_questions_tool`: Extract questions via LLM from markdown
- `validate_question_tool`: Validate extracted question structure
- `refine_question_tool`: Refine low-confidence questions via LLM

## Flow
1. Receive `file_path` in input_data
2. Call `parse_pdf_tool` → get markdown
3. Split markdown into pages
4. For each page:
   a. Call `extract_questions_tool` → get questions[]
   b. For each question:
      - Call `validate_question_tool`
      - If confidence < threshold, call `refine_question_tool`
5. Return {questions, metadata, low_confidence_ids}

## Input Schema
```json
{
  "file_path": "string (required)",
  "confidence_threshold": "number (optional, default 0.6)",
  "source": "string (optional)"
}
```

## Output Schema
```json
{
  "success": true,
  "questions": [...],
  "metadata": {
    "total_pages": 10,
    "questions_extracted": 25,
    "low_confidence_count": 3,
    "markdown_chars": 50000
  },
  "low_confidence_ids": [5, 12, 18]
}
```

## Quality Thresholds
- confidence_threshold: 0.6 (configurable)
- minimum_content_length: 5 chars
- valid_types: ["单选题", "多选题", "判断题", "填空题", "主观题", "未知"]
