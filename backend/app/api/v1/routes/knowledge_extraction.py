from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import os
import shutil
import tempfile
from app.db.session import get_db, AsyncSessionLocal
from app.core.auth import get_current_user
from app.models.user import User
from app.models.knowledge_point import KnowledgePoint, KnowledgePointRelationship
from app.services.document_splitter import split_exam_paper # 复用文档加载逻辑
from app.services.knowledge_extraction import KnowledgeExtractionService
from app.services.knowledge_graph_builder import KnowledgeGraphBuilder
from app.core.config import settings
from app.db.neo4j_utils import create_typed_relation

router = APIRouter()

async def process_knowledge_extraction(
    file_path: str,
    subject_id: int,
    user_id: int
):
    """后台任务：处理知识点提取和图谱构建"""
    async with AsyncSessionLocal() as db:
        try:
            # 1. 加载和切分文档
            # 注意：split_exam_paper 返回的是 Document 对象列表
            documents = split_exam_paper(file_path)
            
            # 2. 提取知识点
            extractor = KnowledgeExtractionService()
            extracted_points_data = await extractor.extract_from_documents(documents, subject_id)
            
            # 3. 保存知识点到数据库
            name_to_id_map = {}
            for kp_data in extracted_points_data:
                # 检查是否存在
                stmt = select(KnowledgePoint).where(
                    KnowledgePoint.subject_id == subject_id,
                    KnowledgePoint.name == kp_data['name']
                )
                result = await db.execute(stmt)
                existing_kp = result.scalar_one_or_none()
                
                if existing_kp:
                    name_to_id_map[kp_data['name']] = existing_kp.id
                    continue
                    
                # 创建新知识点
                new_kp = KnowledgePoint(
                    name=kp_data['name'],
                    description=kp_data['description'],
                    subject_id=subject_id,
                    difficulty=kp_data['difficulty'],
                    creator_id=user_id,
                    code=f"AUTO-{subject_id}-{len(name_to_id_map)}", # 临时生成
                    slug=f"auto-{subject_id}-{kp_data['name']}", # 简单生成
                    is_active=True
                )
                db.add(new_kp)
                await db.flush() # 获取 ID
                await db.refresh(new_kp)
                name_to_id_map[kp_data['name']] = new_kp.id
                
            # 4. 构建关系
            builder = KnowledgeGraphBuilder()
            relationships = builder.build_graph(extracted_points_data)
            optimized_rels = builder.optimize_graph(relationships)
            
            # 5. 保存关系到数据库 (PG & Neo4j)
            for rel in optimized_rels:
                source_id = name_to_id_map.get(rel['source'])
                target_id = name_to_id_map.get(rel['target'])                
                if source_id and target_id and source_id != target_id:
                    # PG
                    new_rel = KnowledgePointRelationship(
                        source_id=source_id,
                        target_id=target_id,
                        relationship_type=rel['type'],
                        weight=rel['weight']
                    )
                    db.add(new_rel)
                    
                    # Neo4j (同步调用，可能需要优化)
                    try:
                        create_typed_relation(source_id, target_id, rel['type'].value, rel['weight'])
                    except Exception as e:
                        print(f"Neo4j sync failed: {e}")

            await db.commit()
            
        except Exception as e:
            print(f"Extraction task failed: {e}")
            await db.rollback()
        finally:
            # 清理临时文件
            if os.path.exists(file_path):
                os.remove(file_path)


@router.post("/extract/{subject_id}", operation_id="从文件提取知识点")
async def extract_knowledge_from_file(
    subject_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    上传教材/文档，自动提取知识点并构建图谱
    """
    if not file.filename.endswith(('.pdf', '.docx', '.txt', '.md')):
        raise HTTPException(status_code=400, detail="不支持的文件格式")
        
    # 保存临时文件
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)
    
    try:
        # 确保文件指针在开始位置
        await file.seek(0)
        # 使用异步读取并写入文件
        content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")
        
    # 添加后台任务
    background_tasks.add_task(
        process_knowledge_extraction,
        file_path,
        subject_id,
        current_user.id
    )
    
    return {"message": "文件已上传，正在后台提取知识点", "filename": file.filename}
