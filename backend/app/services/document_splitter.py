# 文档切分服务,切片教材和试卷
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import UnstructuredWordDocumentLoader  # 添加 DOC 加载器
from langchain_community.document_loaders import UnstructuredMarkdownLoader  # 添加 Markdown 加载器
from langchain.schema import Document
from typing import List
import os
import re  # 添加导入

def split_exam_paper(file_path: str, separators: List[str] = None) -> List[Document]:
    """
    切分试卷文档，按题目分隔
    :param file_path: 试卷文件路径
    :param separators: 分隔符列表，如 ['\n\d+\.', '\n\d+\）']
    :return: 切分后的文档列表
    """
    if separators is None:
        separators = [r'\n\d+\.', r'\n\d+\）', r'\n\d+\s']  # 默认分隔符：1. 1）等    
    # 加载文档
    if file_path.endswith('.pdf'):
        loader = PyPDFLoader(file_path)
    elif file_path.endswith('.txt'):
        loader = TextLoader(file_path)
    elif file_path.endswith('.md'):
        loader = UnstructuredMarkdownLoader(file_path)
    elif file_path.endswith('.doc') or file_path.endswith('.docx'):
        loader = UnstructuredWordDocumentLoader(file_path)
    else:
        raise ValueError("不支持的文件格式")
    documents = loader.load()
    split_docs = []
    for doc in documents:
        text = doc.page_content
        # 使用正则切分
        pattern = '|'.join(separators)
        parts = re.split(pattern, text)
        for i, part in enumerate(parts):
            if part.strip():
                split_docs.append(Document(page_content=part.strip(), metadata={'index': i, **doc.metadata}))    
    return split_docs

