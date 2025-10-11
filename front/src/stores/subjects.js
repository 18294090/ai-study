import { defineStore } from 'pinia';
import { subjectsApi } from '@/services/subjects';

export const useSubjectsStore = defineStore('subjects', {
  state: () => ({
    subjects: [],
    loading: false
  }),

  actions: {
    async fetchSubjects() {
      this.loading = true;
      try {
        const response = await subjectsApi.getSubjects();
        this.subjects = response.data;
        return this.subjects;
      } catch (error) {
        console.error('获取学科列表失败:', error);
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async getSubjectDetail(id) {
      try {
        const response = await subjectsApi.getSubjectDetail(id);
        return response.data;
      } catch (error) {
        console.error('获取学科详情失败:', error);
        throw error;
      }
    },

    async createSubject(data) {
      try {
        const response = await subjectsApi.createSubject(data);
        await this.fetchSubjects();
        return response.data;
      } catch (error) {
        console.error('创建学科失败:', error);
        throw error;
      }
    },

    async updateSubject(id, data) {
      try {
        const response = await subjectsApi.updateSubject(id, data);
        await this.fetchSubjects();
        return response.data;
      } catch (error) {
        console.error('更新学科失败:', error);
        throw error;
      }
    },

    async deleteSubject(id) {
      try {
        await subjectsApi.deleteSubject(id);
        await this.fetchSubjects();
      } catch (error) {
        console.error('删除学科失败:', error);
        throw error;
      }
    }
  }
});
