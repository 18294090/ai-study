import { defineStore } from 'pinia';
import axios from 'axios';

export const useUserStore = defineStore('users', {
  state: () => ({
    users: [],
  }),
  actions: {
    async fetchUsers() {
      try {
        const response = await axios.get('/api/v1/users');
        this.users = response.data;
      } catch (error) {
        console.error('Failed to fetch users:', error);
      }
    },
    async addUser(userData) {
      try {
        await axios.post('/api/v1/users/register', userData);
        await this.fetchUsers(); // Refresh the user list
      } catch (error) {
        console.error('Failed to add user:', error);
      }
    },
    async updateUser(userId, userData) {
      try {
        await axios.put(`/api/v1/users/${userId}`, userData);
        await this.fetchUsers(); // Refresh the user list
      } catch (error) {
        console.error('Failed to update user:', error);
      }
    },
    async deleteUser(userId) {
      try {
        await axios.delete(`/api/v1/users/${userId}`);
        await this.fetchUsers(); // Refresh the user list
      } catch (error) {
        console.error('Failed to delete user:', error);
      }
    },
  },
});
