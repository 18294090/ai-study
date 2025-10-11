import { defineStore } from 'pinia'
import api from '@/services/api'

export const useBooksStore = defineStore('books', {
  state: () => ({
    books: [],
    loading: false
  }),

  actions: {
    async fetchBooks(subjectId) {
      this.loading = true;
      try {
        const response = await api.get(`/api/v1/subjects/${subjectId}/documents`);
        this.books = response.data;
        return this.books;
      } catch (error) {
        console.error('获取文档列表失败:', error);
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async createBook(data) {
        try {
            const response = await api.post(`/api/v1/subjects/${data.subject_id}/documents`, data);
            this.books.push(response.data);
            return response.data;
        } catch (error) {
            console.error('创建文档失败:', error);
            throw error;
        }
    },
    async updateBook(id, data) {
        try {
            const response = await api.put(`/api/v1/documents/${id}`, data);
            const index = this.books.findIndex(book => book.id === id);
            if (index !== -1) {
                this.books[index] = response.data;
            }
            return response.data;
        }catch (error) {
        console.error('更新文档失败:', error);
        throw error;
        }   
    }
    }
});
