from typing import List, Dict, Any, Optional
import re
import json
from langchain.schema import Document
from langchain.prompts import PromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from app.models.knowledge_point import KnowledgePoint, DifficultyLevel, TeachingRequirement
from app.core.config import settings

class KnowledgeExtractionService:
    def __init__(self):
        # 初始化 LLM，使用本地 Ollama 托管的 deepseek-r1:14b
        try:
            self.llm = ChatOllama(
                model="deepseek-r1:14b",
                temperature=0,
                base_url=settings.OLLAMA_BASE_URL if hasattr(settings, 'OLLAMA_BASE_URL') else "http://localhost:11434"
            )
        except Exception as e:
            self.llm = None
            print(f"Warning: LLM not initialized. Knowledge extraction will use rule-based fallback. Error: {e}")

    async def extract_from_documents(self, documents: List[Document], subject_id: int) -> List[Dict[str, Any]]:
        """
        从文档列表中提取知识点
        """
        extracted_points = []
        
        if self.llm:
            extracted_points = await self._extract_with_llm(documents)
        else:
            extracted_points = self._extract_with_rules(documents)
            
        # 后处理：去重、规范化
        return self._post_process(extracted_points, subject_id)

    async def _extract_with_llm(self, documents: List[Document]) -> List[Dict[str, Any]]:
        """使用 LLM 提取知识点"""
        results = []
        
        # 定义提取 Prompt
        prompt_template = """
        你是一个专业的教育专家。请从以下教材文本中提取关键知识点。
        
        文本内容:
        {text}
        
        请以 JSON 格式返回提取结果，列表包含以下字段:
        - name: 知识点名称
        - description: 知识点详细定义或描述
        - difficulty: 难度 (1-5)
        - importance: 重要性 (High/Medium/Low)
        - keywords: 关键词列表
        
        只返回 JSON 数据，不要包含其他解释。
        """
        
        prompt = PromptTemplate(template=prompt_template, input_variables=["text"])
        chain = prompt | self.llm | StrOutputParser()
        
        # 批量处理文档（这里简化处理，实际可能需要合并小文档或并行处理）
        for doc in documents:
            # 限制文本长度以适应 Token 限制
            text_chunk = doc.page_content[:4000] 
            try:
                response = await chain.ainvoke({"text": text_chunk})
                
                # 清理响应内容
                cleaned_response = response.strip()
                
                # 移除 <think> 标签 (针对 DeepSeek R1 等推理模型)
                cleaned_response = re.sub(r'<think>.*?</think>', '', cleaned_response, flags=re.DOTALL).strip()
                
                # 提取 Markdown 代码块中的 JSON
                json_match = re.search(r'```json\s*(.*?)\s*```', cleaned_response, re.DOTALL)
                if json_match:
                    cleaned_response = json_match.group(1)
                else:
                    # 尝试提取纯代码块
                    code_match = re.search(r'```\s*(.*?)\s*```', cleaned_response, re.DOTALL)
                    if code_match:
                        cleaned_response = code_match.group(1)

                # 解析 JSON
                try:
                    data = json.loads(cleaned_response)
                    if isinstance(data, list):
                        results.extend(data)
                    elif isinstance(data, dict) and "knowledge_points" in data:
                        results.extend(data["knowledge_points"])
                except json.JSONDecodeError:
                    print(f"Failed to parse JSON from LLM response: {response[:100]}...")
            except Exception as e:
                print(f"Error calling LLM: {e}")
                
        return results

    def _extract_with_rules(self, documents: List[Document]) -> List[Dict[str, Any]]:
        """
        基于规则的简单提取（兜底方案）
        假设文档结构良好，如 "1. 知识点名称"
        """
        results = []
        for doc in documents:
            lines = doc.page_content.split('\n')
            for line in lines:
                line = line.strip()
                # 简单规则：匹配 "1. xxx" 或 "1.1 xxx" 形式的标题
                match = re.match(r'^(\d+(\.\d+)*)\.?\s+(.+)$', line)
                if match:
                    name = match.group(3)
                    if len(name) > 2 and len(name) < 50: # 过滤过短或过长的
                        results.append({
                            "name": name,
                            "description": f"从文档提取: {name}",
                            "difficulty": 3,
                            "keywords": [name]
                        })
        return results

    def _post_process(self, raw_points: List[Dict[str, Any]], subject_id: int) -> List[Dict[str, Any]]:
        """后处理：去重、格式化"""
        processed = {}
        
        for item in raw_points:
            name = item.get("name", "").strip()
            if not name:
                continue
                
            if name not in processed:
                processed[name] = {
                    "name": name,
                    "description": item.get("description", name),
                    "subject_id": subject_id,
                    "difficulty": item.get("difficulty", 3),
                    "teaching_requirement": TeachingRequirement.MASTER, # 默认
                    "tags": item.get("keywords", []),
                    "is_active": True
                }
            else:
                # 如果已存在，可以合并描述或增加权重
                pass
                
        return list(processed.values())
