import axios from 'axios';
import { useAuthStore } from '../stores/auth';
import router from '../router';
import { ElMessage } from 'element-plus';

// 创建 axios 实例
const http = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL,
    timeout: 15000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// 设置为全局实例
window.$http = http;

// 从 localStorage 中获取 token 并设置
const token = localStorage.getItem('token');
if (token) {
    http.defaults.headers.common['Authorization'] = `Bearer ${token}`;
}

// 请求拦截器
http.interceptors.request.use(
    (config) => {
        const authStore = useAuthStore();
        if (authStore.token) {
            config.headers.Authorization = `Bearer ${authStore.token}`;
        }
        return config;
    },
    (error) => {
        console.error('Request error:', error);
        return Promise.reject(error);
    }
);

// 响应拦截器
http.interceptors.response.use(
    (response) => {
        // 如果响应包含 code 字段，检查是否为成功状态
        if (response.data.hasOwnProperty('code')) {
            if (response.data.code === 0) {
                return response.data;
            } else {
                ElMessage.error(response.data.msg || '请求失败');
                return Promise.reject(new Error(response.data.msg || '请求失败'));
            }
        }
        return response.data;
    },
    (error) => {
        if (error.response) {
            switch (error.response.status) {
                case 401:
                    ElMessage.error('未授权，请重新登录');
                    router.push('/login');
                    break;
                case 403:
                    ElMessage.error('没有权限执行此操作');
                    break;
                case 404:
                    ElMessage.error('请求的资源不存在');
                    break;
                case 500:
                    ElMessage.error('服务器错误，请稍后重试');
                    break;
                case 422:
                    // 处理验证错误
                    const validationErrors = error.response.data;
                    if (typeof validationErrors === 'object' && validationErrors.detail) {
                        // 如果是验证错误数组，取第一个错误信息
                        const errorMessage = Array.isArray(validationErrors.detail) 
                            ? validationErrors.detail[0]?.msg 
                            : validationErrors.detail;
                        ElMessage.error(typeof errorMessage === 'string' ? errorMessage : '输入数据验证失败');
                    } else {
                        ElMessage.error('输入数据验证失败');
                    }
                    break;
                default:
                    const errorMsg = error.response.data?.detail;
                    ElMessage.error(typeof errorMsg === 'string' ? errorMsg : '请求失败');
            }
        } else {
            ElMessage.error('网络错误，请检查您的网络连接');
        }
        return Promise.reject(error);
    }
);

export default http;
