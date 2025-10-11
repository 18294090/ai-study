import { defineStore } from 'pinia';
import api from '@/services/api';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || null,
    user: null,
  }),

  getters: {
    isAuthenticated: (state) => !!state.token,
  },

  actions: {
    setToken(token) {
      this.token = token;
      localStorage.setItem('token', token);
      // 设置axios默认headers
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    },

    async login(username, password) {
      try {
        // 使用URLSearchParams替代FormData，确保数据格式符合OAuth2规范
        const params = new URLSearchParams();
        params.append('username', username);
        params.append('password', password);
        const response = await api.post('/api/v1/auth/login', params, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        });

        if (response.data.access_token) {
          this.setToken(response.data.access_token);
          await this.fetchUser();
          return true;
        }
        throw new Error('登录失败：未获取到访问令牌');
      } catch (error) {
        console.error('登录失败:', error);
        throw error;
      }
    },

    async fetchUser() {
      try {
        const response = await api.get('/api/v1/auth/me', {
          headers: {
            'Authorization': `Bearer ${this.token}`
          }
        });
        this.user = response.data;
      } catch (error) {
        console.error('获取用户信息失败:', error);
        this.logout();
        throw error;
      }
    },

    logout() {
      this.token = null;
      this.user = null;
      localStorage.removeItem('token');
      // 清除axios默认headers
      delete api.defaults.headers.common['Authorization'];
    },

    async register(userInfo) {
      try {
        const response = await api.post('/api/v1/auth/register', {
          username: userInfo.username,
          email: userInfo.email,
          password: userInfo.password,
          role: 'student'
        });

        if (response.data) {
          await this.login(userInfo.email, userInfo.password);
          return response.data;
        }
      } catch (error) {
        console.error('注册失败:', error);
        throw error;
      }
    },
  }
});
