from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import List, Optional
from datetime import datetime
from app.models.application import SubjectApplication, ClassApplication, ApplicationStatus
from app.schemas.application import SubjectApplicationCreate, ClassApplicationCreate, ApplicationUpdate

class CRUDApplication:
    async def create_subject_application(
        self, db: AsyncSession, *, obj_in: SubjectApplicationCreate
    ) -> SubjectApplication:
        """创建学科加入申请"""
        db_obj = SubjectApplication(
            subject_id=obj_in.subject_id,
            applicant_id=obj_in.applicant_id,
            message=obj_in.message
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def create_class_application(
        self, db: AsyncSession, *, obj_in: ClassApplicationCreate
    ) -> ClassApplication:
        """创建班级加入申请"""
        db_obj = ClassApplication(
            class_id=obj_in.class_id,
            applicant_id=obj_in.applicant_id,
            message=obj_in.message
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_subject_application(
        self, db: AsyncSession, *, id: int
    ) -> Optional[SubjectApplication]:
        """获取学科申请"""
        result = await db.execute(select(SubjectApplication).where(SubjectApplication.id == id))
        return result.scalar_one_or_none()

    async def get_class_application(
        self, db: AsyncSession, *, id: int
    ) -> Optional[ClassApplication]:
        """获取班级申请"""
        result = await db.execute(select(ClassApplication).where(ClassApplication.id == id))
        return result.scalar_one_or_none()

    async def get_subject_applications_by_subject(
        self, db: AsyncSession, *, subject_id: int, status: Optional[ApplicationStatus] = None
    ) -> List[SubjectApplication]:
        """获取学科的所有申请"""
        query = select(SubjectApplication).where(SubjectApplication.subject_id == subject_id)
        if status:
            query = query.where(SubjectApplication.status == status)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_class_applications_by_class(
        self, db: AsyncSession, *, class_id: int, status: Optional[ApplicationStatus] = None
    ) -> List[ClassApplication]:
        """获取班级的所有申请"""
        query = select(ClassApplication).where(ClassApplication.class_id == class_id)
        if status:
            query = query.where(ClassApplication.status == status)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_applications_by_applicant(
        self, db: AsyncSession, *, applicant_id: int
    ) -> List[SubjectApplication | ClassApplication]:
        """获取用户的所有申请"""
        subject_apps = await db.execute(
            select(SubjectApplication).where(SubjectApplication.applicant_id == applicant_id)
        )
        class_apps = await db.execute(
            select(ClassApplication).where(ClassApplication.applicant_id == applicant_id)
        )
        return list(subject_apps.scalars().all()) + list(class_apps.scalars().all())

    async def update_subject_application(
        self, db: AsyncSession, *, id: int, obj_in: ApplicationUpdate
    ) -> Optional[SubjectApplication]:
        """更新学科申请状态"""
        update_data = obj_in.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        query = (
            update(SubjectApplication)
            .where(SubjectApplication.id == id)
            .values(**update_data)
        )
        await db.execute(query)
        await db.commit()

        return await self.get_subject_application(db, id=id)

    async def update_class_application(
        self, db: AsyncSession, *, id: int, obj_in: ApplicationUpdate
    ) -> Optional[ClassApplication]:
        """更新班级申请状态"""
        update_data = obj_in.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        query = (
            update(ClassApplication)
            .where(ClassApplication.id == id)
            .values(**update_data)
        )
        await db.execute(query)
        await db.commit()

        return await self.get_class_application(db, id=id)

    async def delete_subject_application(self, db: AsyncSession, *, id: int) -> bool:
        """删除学科申请"""
        result = await db.execute(
            delete(SubjectApplication).where(SubjectApplication.id == id)
        )
        await db.commit()
        return result.rowcount > 0

    async def delete_class_application(self, db: AsyncSession, *, id: int) -> bool:
        """删除班级申请"""
        result = await db.execute(
            delete(ClassApplication).where(ClassApplication.id == id)
        )
        await db.commit()
        return result.rowcount > 0

crud_application = CRUDApplication()