import axios from 'axios';
import { ElMessage } from 'element-plus';

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  timeout: 10000,
  withCredentials: true,
});

// 请求拦截器确保每个请求都带上最新的token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, error => {
  return Promise.reject(error);
});

// 响应拦截器处理401错误
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
    }
    const message = error.response?.data?.detail || '请求失败';
    ElMessage.error(message);
    return Promise.reject(error);
  }
);
export default api;


