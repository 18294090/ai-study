import api from './api';

export const subjectsApi = {
  getSubjects: () => api.get('/api/v1/subjects/'),
  getSubjectDetail: (id) => api.get(`/api/v1/subjects/${id}`),
  createSubject: (data) => api.post('/api/v1/subjects/', data),
  updateSubject: (id, data) => api.put(`/api/v1/subjects/${id}`, data),
  deleteSubject: (id) => api.delete(`/api/v1/subjects/${id}`)
};
