<template>
  <div class="register-container">
    <!-- 左侧品牌区 -->
    <div class="brand-section">
      <div class="brand-content">
        <h1>加入我们</h1>
        <p class="slogan">开启智慧学习之旅</p>
        <div class="features">
          <div class="feature-item">
            <el-icon><UserFilled /></el-icon>
            <span>专业的题库管理</span>
          </div>
          <div class="feature-item">
            <el-icon><Edit /></el-icon>
            <span>便捷的学习工具</span>
          </div>
          <div class="feature-item">
            <el-icon><Promotion /></el-icon>
            <span>智能的学习分析</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧注册区 -->
    <div class="register-section">
      <div class="register-box">
        <h2>创建新账号</h2>
        <p class="welcome-text">请填写以下信息完成注册</p>

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              :prefix-icon="User"
              size="large"
            />
          </el-form-item>
          <el-form-item prop="email">
            <el-input
              v-model="form.email"
              placeholder="请输入邮箱"
              :prefix-icon="Message"
              size="large"
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              show-password
              size="large"
            />
          </el-form-item>
          <el-form-item prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="请确认密码"
              :prefix-icon="Key"
              show-password
              size="large"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="loading" @click="handleRegister" class="submit-btn" size="large">
              立即注册
            </el-button>
          </el-form-item>
        </el-form>

        <div class="login-link">
          已有账号？<router-link to="/login">立即登录</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { ElMessage } from 'element-plus';
import {
  User, Lock, Message, Key,
  UserFilled, Edit, Promotion
} from '@element-plus/icons-vue';

const router = useRouter();
const authStore = useAuthStore();
const formRef = ref(null);  // 添加表单引用
const loading = ref(false);
const form = ref({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
});

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== form.value.password) {
          callback(new Error('两次输入的密码不一致'));
        } else {
          callback();
        }
      },
      trigger: 'blur'
    }
  ]
};

const handleRegister = async () => {
  if (!formRef.value) return;
  
  try {
    const valid = await formRef.value.validate();
    if (valid) {
      loading.value = true;
      await authStore.register({
        username: form.value.username,
        email: form.value.email,
        password: form.value.password
      });
      ElMessage.success('注册成功！');
      router.push('/login');
    }
  } catch (error) {
    ElMessage.error(error.message || '注册失败，请重试');
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.register-container {
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

.register-section {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.register-box {
  width: 100%;
  max-width: 420px;
  padding: 40px;
  background: white;
  border-radius: 20px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.08);
}

.register-box h2 {
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

.submit-btn {
  width: 100%;
  height: 45px;
  font-size: 16px;
  border-radius: 12px;
  background: linear-gradient(45deg, #1890ff, #1e80ff);
  border: none;
  transition: all 0.3s ease;
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(30, 128, 255, 0.3);
}

.login-link {
  text-align: center;
  margin-top: 20px;
  color: #666;
}

.login-link a {
  color: #1e80ff;
  text-decoration: none;
  font-weight: 500;
  margin-left: 5px;
}

.login-link a:hover {
  text-decoration: underline;
}

@media (max-width: 1024px) {
  .brand-section {
    display: none;
  }
}
</style>

