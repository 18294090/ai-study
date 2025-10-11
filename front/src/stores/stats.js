import { defineStore } from 'pinia';
import axios from 'axios';

export const useStatsStore = defineStore('stats', {
  state: () => ({
    stats: {
      documents_count: 0,
      questions_count: 0
    },
    loading: false
  }),

  actions: {
    async fetchStats() {
      this.loading = true;
      try {
        const response = await axios.get('/api/v1/books/stats', {
          headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
        });
        this.stats = response.data;
      } catch (error) {
        console.error('获取统计信息失败:', error);
      } finally {
        this.loading = false;
      }
    }
  }
});
