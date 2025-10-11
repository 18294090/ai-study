import api from './api';

const subjectService = {
  getAll() {
    return api.get('/subjects/');
  },
  getById(id) {
    return api.get(`/subjects/${id}`);
  },
  create(data) {
    return api.post('/subjects/', data);
  },
  update(id, data) {
    return api.put(`/subjects/${id}`, data);
  },
  delete(id) {
    return api.delete(`/subjects/${id}`);
  },
};
export default subjectService;
