import api from './api';

export const questionsApi = {
  getQuestions: (params) => api.get('/api/v1/questions/', { params }),
  createQuestion: (data) => api.post('/api/v1/questions/', data),
  searchQuestions: (params) => api.get('/api/v1/questions//search', { params }),
  batchImport: (data) => api.post('/api/v1/questions//batch-import', data),
  addComment: (questionId, data) => api.post(`/api/v1/questions/${questionId}/comments`, data),
  updateQuestion : (questionId, data) => api.put(`/api/v1/questions/${questionId}`, data)
};
