from typing import Any, Dict, List, Optional
from sqlalchemy import select, insert, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.knowledge_point import (
    KnowledgePoint,
    knowledge_point_closure,
)
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from app.utils.knowledge_point_identifiers import (
    generate_knowledge_point_code,
    generate_knowledge_point_slug,
)

async def create_knowledge_point(
    session: AsyncSession,
    name: str,
    subject_id: int,  # 显式添加 subject_id 参数
    parent_id: Optional[int] = None,
    **kwargs: Any,
) -> KnowledgePoint:
    """创建知识点（在事务中）。
    说明：事件监听器会维护闭包表、path、depth。返回已刷新的 ORM 实例。
    """
    # 移除 kwargs 中的 subject_id 和 subject，以避免冲突
    kwargs.pop('subject_id', None)
    kwargs.pop('subject', None)
    creator_id = kwargs.pop('creator_id', None)
    if creator_id is None:
        raise ValueError("creator_id is required to create a knowledge point")
    code = kwargs.pop('code', generate_knowledge_point_code(subject_id))
    slug = kwargs.pop('slug', generate_knowledge_point_slug(name, subject_id))
    kp = KnowledgePoint(
        name=name,
        code=code,
        slug=slug,
        subject_id=subject_id,
        parent_id=parent_id,
        creator_id=creator_id,
        **kwargs,
    )
    session.add(kp)
    await session.flush()  # 触发 after_insert 事件，确保 kp.id 可用
    await session.refresh(kp)
    return kp


async def add_closure_for_insert(
    session: AsyncSession, node_id: int, parent_id: Optional[int]
) -> None:
    """在插入新节点后，维护闭包表以及节点的 path/depth。

    - 永远插入 self->self(depth=0)
    - 若有父节点：
        - 复制父节点所有祖先关系，形成这些祖先到新节点的关系，depth 逐级 +1
        - 插入 parent -> node depth=1
        - 同时更新新节点的 path、depth
    - 若无父节点：path=自身id，depth=1
    """
    # 确保节点存在
    kp = await session.get(KnowledgePoint, node_id)
    if not kp:
        raise ValueError(f"知识点 {node_id} 不存在")

    # 1) 插入 self 关系
    await session.execute(
        insert(knowledge_point_closure).values(
            ancestor_id=node_id, descendant_id=node_id, depth=0
        )
    )

    # 2) 有父节点则继承祖先关系
    if parent_id is not None:
        # 取父节点的所有祖先（包含父->父 depth=0）
        stmt = select(
            knowledge_point_closure.c.ancestor_id,
            knowledge_point_closure.c.depth,
        ).where(knowledge_point_closure.c.descendant_id == parent_id)
        res = await session.execute(stmt)
        rows = res.fetchall()
        # 插入每个祖先到新节点的关系，depth+1
        batch = [
            {
                "ancestor_id": anc,
                "descendant_id": node_id,
                "depth": int(d) + 1,
            }
            for (anc, d) in rows
        ]
        if batch:
            await session.execute(insert(knowledge_point_closure), batch)

        # 更新 path/depth：基于父节点
        parent = await session.get(KnowledgePoint, parent_id)
        if parent:
            kp.depth = (parent.depth or 0) + 1
            if parent.path:
                kp.path = f"{parent.path}/{kp.id}"
            else:
                kp.path = f"{parent.id}/{kp.id}"
    else:
        # 根节点
        kp.depth = 1
        kp.path = str(kp.id)

    await session.flush()

async def _get_descendant_ids(session: AsyncSession, node_id: int) -> List[int]:
    stmt = select(knowledge_point_closure.c.descendant_id).where(
        knowledge_point_closure.c.ancestor_id == node_id
    )
    res = await session.execute(stmt)
    return [row[0] for row in res.fetchall()]


async def _get_ancestor_ids(session: AsyncSession, node_id: int) -> List[int]:
    stmt = select(knowledge_point_closure.c.ancestor_id).where(
        knowledge_point_closure.c.descendant_id == node_id
    )
    res = await session.execute(stmt)
    return [row[0] for row in res.fetchall()]


async def move_knowledge_point(
    session: AsyncSession, node_id: int, new_parent_id: Optional[int]
) -> Optional[KnowledgePoint]:
    """将节点移动到 new_parent_id。
    会检测环（不能把节点移动到自己的子孙）。
    """
    kp = await session.get(KnowledgePoint, node_id)
    if not kp:
        raise ValueError(f"知识点 {node_id} 不存在")

    # 若 new_parent_id 为 None，则允许成为根
    if new_parent_id is not None:
        # 检查 new_parent 是否是 node 的后代，若是则会产生环
        descendants = await _get_descendant_ids(session, node_id)
        if new_parent_id in descendants:
            raise ValueError("无法将节点移动到其子孙节点，会形成环")

        # 检查 new_parent 是否存在
        new_parent = await session.get(KnowledgePoint, new_parent_id)
        if not new_parent:
            raise ValueError(f"父节点 {new_parent_id} 不存在")

    kp.parent_id = new_parent_id
    kp.updated_at = datetime.utcnow()
    await session.flush()  # 触发 before_update/after_update 事件以维护闭包/path/depth
    await session.refresh(kp)
    # 简化实现：移动后重建整个闭包表，确保数据正确
    await rebuild_closure(session)
    await session.flush()
    return kp


async def delete_knowledge_point(
    session: AsyncSession, node_id: int, reparent_children: bool = False
) -> bool:
    """删除知识点。
    reparent_children=True 时把直接子节点上移到被删除节点的 parent。
    否则 cascade 删除子树（children cascade 已在模型中设置）。
    """
    kp = await session.get(KnowledgePoint, node_id)
    if not kp:
        raise ValueError(f"知识点 {node_id} 不存在")
    if reparent_children:
        # 把直接子节点的 parent 指向当前节点的 parent
        children = list(kp.children)
        for c in children:
            c.parent_id = kp.parent_id
        await session.flush()
    await session.delete(kp)
    await session.flush()
    return True


async def get_subtree(session: AsyncSession, node_id: int) -> List[Dict[str, Any]]:
    """返回子树所有节点的 ORM 数据（按 depth 升序）。"""
    stmt = select(KnowledgePoint).join(
        knowledge_point_closure,
        knowledge_point_closure.c.descendant_id == KnowledgePoint.id,
    ).where(knowledge_point_closure.c.ancestor_id == node_id).order_by(knowledge_point_closure.c.depth)
    res = await session.execute(stmt)
    rows = [r[0] for r in res.fetchall()]
    return [
        {
            "id": n.id,
            "name": n.name,
            "parent_id": n.parent_id,
            "path": n.path,
            "depth": n.depth,
        }
        for n in rows
    ]


async def get_ancestors(session: AsyncSession, node_id: int) -> List[Dict[str, Any]]:
    stmt = select(KnowledgePoint).join(
        knowledge_point_closure,
        knowledge_point_closure.c.ancestor_id == KnowledgePoint.id,
    ).where(knowledge_point_closure.c.descendant_id == node_id).order_by(knowledge_point_closure.c.depth)
    res = await session.execute(stmt)
    rows = [r[0] for r in res.fetchall()]
    return [
        {"id": n.id, "name": n.name, "path": n.path, "depth": n.depth} for n in rows
    ]


async def build_tree(session: AsyncSession, root_id: int) -> Dict[str, Any]:
    """基于 parent_id 构建嵌套树结构（从 root_id 开始）。

    返回字典：{id, name, children: [...]}，便于前端展示。
    """
    # 获取子树节点（ORM 实例）
    stmt = select(KnowledgePoint).join(
        knowledge_point_closure,
        knowledge_point_closure.c.descendant_id == KnowledgePoint.id,
    ).where(knowledge_point_closure.c.ancestor_id == root_id).order_by(KnowledgePoint.depth)
    res = await session.execute(stmt)
    nodes = [r[0] for r in res.fetchall()]

    # 映射 id->node
    node_map: Dict[int, Dict[str, Any]] = {}
    children_map: Dict[Optional[int], List[Dict[str, Any]]] = {}
    for n in nodes:
        node_map[n.id] = {"id": n.id, "name": n.name, "parent_id": n.parent_id, "children": []}
        children_map.setdefault(n.parent_id, []).append(node_map[n.id])

    # 连接父子
    for nid, node in node_map.items():
        node_parent = node.get("parent_id")
        if node_parent in node_map:
            node_map[node_parent]["children"].append(node)

    # 返回根节点结构
    root = node_map.get(root_id)
    if not root:
        # 如果 root 本身不存在，尝试加载 it
        kp = await session.get(KnowledgePoint, root_id)
        if not kp:
            return {}
        root = {"id": kp.id, "name": kp.name, "parent_id": kp.parent_id, "children": children_map.get(kp.id, [])}
    return root


async def rebuild_closure(session: AsyncSession) -> None:
    """重建整个 closure 表（谨慎，建议离线或维护窗口运行）。

    算法：清空 closure，然后为每个节点插入自身->自身; 再基于 parent 指针逐层插入祖先关系。
    适用于表不大或维护窗口场景。
    """
    # 删除所有 existing 记录
    await session.execute(delete(knowledge_point_closure))
    await session.flush()

    # 插入 self relations
    stmt_self = insert(knowledge_point_closure).from_select(
        ["ancestor_id", "descendant_id", "depth"],
        select(KnowledgePoint.id, KnowledgePoint.id, 0),
    )
    await session.execute(stmt_self)
    await session.flush()

    # 为每个节点沿 parent 链插入祖先关系
    # 取所有节点 id
    res = await session.execute(select(KnowledgePoint.id, KnowledgePoint.parent_id))
    rows = res.fetchall()
    id_parent = {r[0]: r[1] for r in rows}

    # 对每个节点，walk upward 插入 ancestor关系
    for node_id, parent_id in id_parent.items():
        current_parent = parent_id
        depth = 1
        values = []
        while current_parent is not None:
            values.append({"ancestor_id": current_parent, "descendant_id": node_id, "depth": depth})
            depth += 1
            current_parent = id_parent.get(current_parent)
        if values:
            try:
                await session.execute(insert(knowledge_point_closure), values)
            except IntegrityError:
                # 忽略重复插入
                pass
    await session.flush()


# End of service
