import api from './api';

const questionService = {
  search(params) {
    return api.get('/questions/search', { params });
  },
  create(data) {
    // 创建题目通常涉及文件上传，需要使用 FormData
    const formData = new FormData();
    for (const key in data) {
      if (key === 'files') {
        data.files.forEach(file => formData.append('files', file));
      } else {
        formData.append(key, data[key]);
      }
    }
    return api.post('/questions/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  // ... 其他方法
};

export default questionService;
