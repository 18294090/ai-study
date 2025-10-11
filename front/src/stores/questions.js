import { defineStore } from 'pinia';
import { questionsApi } from '@/services/questions';

export const useQuestionsStore = defineStore('questions', {
  state: () => ({
    questions: [],
    totalCount: 0,
    currentPage: 1,
    pageSize: 10,
    loading: false,
    error: null
  }),
  actions: {
    async fetchQuestions(params = {}) {
      this.loading = true;
      try {
        const response = await questionsApi.getQuestions({
          page: this.currentPage,
          per_page: this.pageSize,
          ...params
        });
        this.questions = response.data.items;
        this.totalCount = response.data.total;
      } catch (error) {
        this.error = error.message;
      } finally {
        this.loading = false;
      }
    },
    async createQuestion(questionData) {
      try {
        const response = await questionsApi.createQuestion(questionData);
        return response.data;
      } catch (error) {
        this.error = error.message;
        throw error;
      }
    }
  }
});
