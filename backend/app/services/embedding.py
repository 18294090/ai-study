# 文档向量化服务
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import UnstructuredWordDocumentLoader
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain.schema import Document
from typing import List
import os
from langchain_ollama import OllamaEmbeddings  # 更新导入
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.VectorStore import DocumentChunk
from app.services.document_splitter import split_exam_paper

# 初始化本地 Ollama 嵌入模型（更精准的 bge-m3）
embeddings = OllamaEmbeddings(model="bge-m3", base_url="http://localhost:11434")


