from typing import List, Dict, Any, Tuple
import networkx as nx
from app.models.knowledge_point import KnowledgePoint, RelationshipType

class KnowledgeGraphBuilder:
    def __init__(self):
        self.graph = nx.DiGraph()

    def build_graph(self, knowledge_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        构建知识图谱关系
        返回关系列表 [{"source": name, "target": name, "type": type}]
        """
        relationships = []
        
        # 1. 基于层级构建 (Hierarchy)
        # 假设输入列表已经包含某种层级信息，或者我们通过名称推断
        # 例如：如果 A 是 "函数"，B 是 "一次函数"，则 A -> B (Contains)
        
        # 简单包含关系检测
        sorted_points = sorted(knowledge_points, key=lambda x: len(x['name']))
        
        for i, kp1 in enumerate(sorted_points):
            for kp2 in sorted_points[i+1:]:
                if kp1['name'] in kp2['name']:
                    # kp1 (短) 可能是 kp2 (长) 的父级
                    # 例如 "函数" -> "一次函数"
                    relationships.append({
                        "source": kp1['name'],
                        "target": kp2['name'],
                        "type": RelationshipType.CONTAINS,
                        "weight": 1.0
                    })
                elif kp1['name'] in kp2.get('description', ''):
                    # kp2 的描述中提到了 kp1，可能是依赖关系
                    relationships.append({
                        "source": kp1['name'],
                        "target": kp2['name'],
                        "type": RelationshipType.PREREQUISITE,
                        "weight": 0.8
                    })

        # 2. 基于共现分析 (Co-occurrence) - 如果有原始文本上下文
        # 这里简化处理，仅基于名称和描述
        
        return relationships

    def optimize_graph(self, relationships: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        优化图结构，移除循环，修剪弱连接
        """
        G = nx.DiGraph()
        for rel in relationships:
            G.add_edge(rel['source'], rel['target'], type=rel['type'], weight=rel['weight'])
            
        # 移除循环依赖
        try:
            cycles = list(nx.simple_cycles(G))
            for cycle in cycles:
                # 简单策略：移除环中最后一条边
                if len(cycle) > 1:
                    u, v = cycle[-2], cycle[-1]
                    if G.has_edge(u, v):
                        G.remove_edge(u, v)
        except Exception:
            pass
            
        # 转换回列表
        optimized_rels = []
        for u, v, data in G.edges(data=True):
            optimized_rels.append({
                "source": u,
                "target": v,
                "type": data['type'],
                "weight": data['weight']
            })
            
        return optimized_rels
