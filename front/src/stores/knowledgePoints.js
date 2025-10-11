import { defineStore } from 'pinia';
import api from '@/services/api';

export const useKnowledgePointsStore = defineStore('knowledgePoints', {
  state: () => ({
    knowledgePoints: [],
    loading: false
  }),

  actions: {
    async fetchKnowledgePoints(subjectId) {
      this.loading = true;
      try {
        const response = await api.get(`/api/v1/subjects/${subjectId}/knowledge-points`);
        this.knowledgePoints = response.data;
        return this.knowledgePoints;
      } catch (error) {
        console.error('获取知识点列表失败:', error);
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async createKnowledgePoint(data) {
      try {
        const response = await api.post(`/api/v1/subjects/${data.subject_id}/knowledge-points`, data);
        return response.data;
      } catch (error) {
        console.error('创建知识点失败:', error);
        throw error;
      }
    },

    async updateKnowledgePoint(id, data) {
      try {
        const response = await api.put(`/api/v1/knowledge-points/${id}`, data);
        return response.data;
      } catch (error) {
        console.error('更新知识点失败:', error);
        throw error;
      }
    },

    async deleteKnowledgePoint(id) {
      try {
        await api.delete(`/api/v1/knowledge-points/${id}`);
      } catch (error) {
        console.error('删除知识点失败:', error);
        throw error;
      }
    }
  }
});
