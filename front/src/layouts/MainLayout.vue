# MainLayout.vue，应用的主布局组件
<template>
  <el-container class="layout-container">
    <el-aside width="200px" class="aside">
      <div class="logo">
        题库管理系统
      </div>
      <el-menu
        :router="true"
        :default-active="activeMenu"
        background-color="#304156"
        text-color="#fff"
      >
        <el-menu-item index="/">
          <el-icon><Histogram /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/subjects">
          <el-icon><Reading /></el-icon>
          <span>科目管理</span>
        </el-menu-item>
        <el-menu-item index="/questions">
          <el-icon><Document /></el-icon>
          <span>题目管理</span>
        </el-menu-item>
        
        <el-menu-item index="/mistake-book">
          <el-icon><Warning /></el-icon>
          <span>错题本</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-icon class="fold-btn" @click="toggleSidebar">
            <Fold v-if="!collapsed" />
            <Expand v-else />
          </el-icon>
        </div>
        <div class="header-right">
          <el-dropdown trigger="click">
            <span class="user-info">
              {{ authStore.user?.username || '加载中...' }}
              <el-icon><CaretBottom /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="$router.push('/profile')">
                  个人中心
                </el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <el-main v-loading="loading">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { ElMessage } from 'element-plus';
import {
  Histogram,
  Reading,
  Document,
  Connection,
  Warning,
  Fold,
  Expand,
  CaretBottom
} from '@element-plus/icons-vue';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const collapsed = ref(false);
const loading = ref(true);

const activeMenu = computed(() => route.path);

onMounted(async () => {
  try {
    await authStore.fetchUser();
  } catch (error) {
    ElMessage.error('获取用户信息失败');
    router.push('/login');
  } finally {
    loading.value = false;
  }
});

const toggleSidebar = () => {
  collapsed.value = !collapsed.value;
};

const handleLogout = async () => {
  try {
    await authStore.logout();
    router.push('/login');
  } catch (error) {
    ElMessage.error('退出失败');
  }
};
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.aside {
  background-color: #304156;
  color: white;
}

.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  font-size: 20px;
  font-weight: bold;
  color: white;
  background-color: #2b3649;
}

.header {
  background-color: white;
  border-bottom: 1px solid #dcdfe6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.header-right {
  cursor: pointer;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fold-btn {
  font-size: 20px;
  cursor: pointer;
}

:deep(.el-menu) {
  border-right: none;
}

:deep(.el-menu-item) {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>