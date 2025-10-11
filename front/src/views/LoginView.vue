<template>
  <div class="login-container">
    <!-- 左侧品牌区 -->
    <div class="brand-section">
      <div class="brand-content">
        <h1>题库管理系统</h1>
        <p class="slogan">智慧教学 · 高效管理</p>
        <div class="features">
          <div class="feature-item">
            <el-icon><Document /></el-icon>
            <span>智能题库管理</span>
          </div>
          <div class="feature-item">
            <el-icon><DataAnalysis /></el-icon>
            <span>数据分析</span>
          </div>
          <div class="feature-item">
            <el-icon><Connection /></el-icon>
            <span>知识点关联</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧登录区 -->
    <div class="login-section">
      <div class="login-box">
        <h2>欢迎登录</h2>
        <p class="welcome-text">请使用您的账号密码登录系统</p>
        
        <el-form
          ref="loginFormRef"
          :model="loginData"
          :rules="loginRules"
          @submit.prevent="handleLogin"
        >
          <el-form-item prop="username">
            <el-input
              v-model="loginData.username"
              placeholder="请输入用户名"
              :prefix-icon="User"
              size="large"
              clearable
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="loginData.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              show-password
              size="large"
              clearable
            />
          </el-form-item>
          <el-form-item>
            <el-button :loading="loading" type="primary" native-type="submit" class="login-button">
              登 录
            </el-button>
          </el-form-item>
        </el-form>

        <div class="additional-links">
          <el-checkbox v-model="rememberMe">记住我</el-checkbox>
          <a href="#" class="forgot-password">忘记密码？</a>
        </div>

        <div class="footer-links">
          <span>还没有账号？</span>
          <router-link to="/register" class="register-link">立即注册</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick } from 'vue';
import { useAuthStore } from '../stores/auth';
import { useRouter, useRoute } from 'vue-router';
import { ElMessage } from 'element-plus';
import { 
  User, 
  Lock,
  Document,
  DataAnalysis,
  Connection
} from '@element-plus/icons-vue';

const router = useRouter();
const authStore = useAuthStore();
const route = useRoute();
const loginFormRef = ref(null);
const loading = ref(false);

const loginData = reactive({
  username: '',
  password: '',
});

const loginRules = reactive({
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, message: '用户名长度至少为2个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 3, message: '密码长度至少为3个字符', trigger: 'blur' }
  ],
});

const handleLogin = async () => {
  if (!loginFormRef.value) return;  
  try {
    await loginFormRef.value.validate();
    loading.value = true;    
    await authStore.login(loginData.username, loginData.password);
    ElMessage.success('登录成功！');    
    // 优化跳转逻辑
    const redirectPath = route.query.redirect || '/';
    // 确保跳转完成
    await router.replace(redirectPath);
  } catch (error) {
    // 错误处理
    if (error.response) {
      // 服务器返回的错误
      switch (error.response.status) {
        case 401:
          ElMessage.error('用户名或密码错误');
          break;
        case 422:
          ElMessage.error('请输入有效的用户名和密码');
          break;
        case 429:
          ElMessage.error('登录尝试次数过多，请稍后再试');
          break;
        default:
          ElMessage.error('登录失败，请稍后重试');
      }
    } else if (error.message) {
      // 表单验证错误
      ElMessage.warning(error.message);
    } else {
      // 网络错误
      ElMessage.error('网络错误，请检查网络连接');
    }    
    // 清空密码
    loginData.password = '';
    // 聚焦用户名输入框
    nextTick(() => {
      loginFormRef.value?.fields?.username?.focus();
    });
  } finally {
    loading.value = false;
  }
};

// 添加记住我功能
const rememberMe = ref(false);
</script>

<style scoped>
.login-container {
  display: flex;
  min-height: 100vh;
  background: #f5f7fa;
}

.brand-section {
  flex: 1;
  background: linear-gradient(135deg, #1890ff 0%, #1e80ff 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  padding: 40px;
}

.brand-content {
  max-width: 500px;
}

.brand-content h1 {
  font-size: 3rem;
  margin-bottom: 1rem;
  font-weight: 600;
}

.slogan {
  font-size: 1.5rem;
  margin-bottom: 3rem;
  opacity: 0.9;
}

.features {
  display: grid;
  gap: 20px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 1.1rem;
  padding: 15px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  backdrop-filter: blur(10px);
  transition: transform 0.3s ease;
}

.feature-item:hover {
  transform: translateX(10px);
}

.login-section {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.login-box {
  width: 100%;
  max-width: 420px;
  padding: 40px;
  background: white;
  border-radius: 20px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.08);
}

.login-box h2 {
  font-size: 28px;
  font-weight: 600;
  color: #1e1e1e;
  margin-bottom: 10px;
}

.welcome-text {
  color: #666;
  margin-bottom: 30px;
}

:deep(.el-input__wrapper) {
  box-shadow: none !important;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 12px 15px;
  transition: all 0.3s ease;
}

:deep(.el-input__wrapper:hover) {
  border-color: #1e80ff;
}

:deep(.el-input__wrapper.is-focus) {
  border-color: #1e80ff;
  box-shadow: 0 0 0 2px rgba(30, 128, 255, 0.1) !important;
}

.login-button {
  width: 100%;
  height: 45px;
  font-size: 16px;
  border-radius: 12px;
  background: linear-gradient(45deg, #1890ff, #1e80ff);
  border: none;
  transition: all 0.3s ease;
}

.login-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(30, 128, 255, 0.3);
}

.additional-links {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 20px 0;
}

.forgot-password {
  color: #1e80ff;
  text-decoration: none;
  font-size: 14px;
}

.footer-links {
  text-align: center;
  margin-top: 30px;
  color: #666;
}

.register-link {
  color: #1e80ff;
  font-weight: 500;
  text-decoration: none;
  margin-left: 5px;
}

.register-link:hover {
  text-decoration: underline;
}

@media (max-width: 1024px) {
  .brand-section {
    display: none;
  }
}
</style>
