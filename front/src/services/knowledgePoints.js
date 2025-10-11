import api from './api';

export const knowledgePointsApi = {
  // 获取指定学科的所有知识点
  getKnowledgePoints: (subjectId) => 
    api.get(`/api/v1/subjects/${subjectId}/knowledge-points`),
    
  // 创建知识点
  createKnowledgePoint: (data) => 
    api.post(`/api/v1/subjects/${data.subject_id}/knowledge-points`, data),
    
  // 更新知识点
  updateKnowledgePoint: (id, data) => 
    api.put(`/api/v1/knowledge-points/${id}`, data),
    
  // 删除知识点
  deleteKnowledgePoint: (id) => 
    api.delete(`/api/v1/knowledge-points/${id}`)
};
