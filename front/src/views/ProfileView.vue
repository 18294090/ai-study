<template>
  <div class="profile-container">
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card class="profile-card">
          <template #header>
            <div class="card-header">
              <span>个人资料</span>
              <el-button type="primary" size="small" @click="toggleEdit">
                {{ isEditing ? '保存' : '编辑' }}
              </el-button>
            </div>
          </template>
          <div class="avatar-container">
            <el-avatar :size="100" :src="userInfo.avatar || defaultAvatar" />
            <el-upload
              v-if="isEditing"
              class="avatar-uploader"
              action="/api/v1/users/avatar"
              :show-file-list="false"
              :on-success="handleAvatarSuccess"
              :before-upload="beforeAvatarUpload"
            >
              <el-button size="small">更换头像</el-button>
            </el-upload>
          </div>
          <el-form ref="formRef" :model="userInfo" :disabled="!isEditing">
            <el-form-item label="用户名">
              <el-input v-model="userInfo.username" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="userInfo.email" />
            </el-form-item>
            <el-form-item label="角色">
              <el-tag>{{ userInfo.role }}</el-tag>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>修改密码</span>
            </div>
          </template>
          <el-form
            ref="passwordFormRef"
            :model="passwordForm"
            :rules="passwordRules"
            label-width="100px"
          >
            <el-form-item label="当前密码" prop="currentPassword">
              <el-input
                v-model="passwordForm.currentPassword"
                type="password"
                show-password
              />
            </el-form-item>
            <el-form-item label="新密码" prop="newPassword">
              <el-input
                v-model="passwordForm.newPassword"
                type="password"
                show-password
              />
            </el-form-item>
            <el-form-item label="确认新密码" prop="confirmPassword">
              <el-input
                v-model="passwordForm.confirmPassword"
                type="password"
                show-password
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="changePassword">
                修改密码
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
const isEditing = ref(false);
const defaultAvatar = '/default-avatar.png';

const userInfo = ref({
  username: '',
  email: '',
  role: '',
  avatar: ''
});

const passwordForm = ref({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
});

const passwordRules = {
  currentPassword: [
    { required: true, message: '请输入当前密码', trigger: 'blur' }
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能小于6位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== passwordForm.value.newPassword) {
          callback(new Error('两次输入的密码不一致'));
        } else {
          callback();
        }
      },
      trigger: 'blur'
    }
  ]
};

const toggleEdit = async () => {
  if (isEditing.value) {
    try {
      // 保存用户信息
      await authStore.updateProfile(userInfo.value);
      ElMessage.success('保存成功');
    } catch (error) {
      ElMessage.error('保存失败');
      return;
    }
  }
  isEditing.value = !isEditing.value;
};

const changePassword = async () => {
  try {
    await authStore.changePassword(passwordForm.value);
    ElMessage.success('密码修改成功');
    passwordForm.value = {
      currentPassword: '',
      newPassword: '',
      confirmPassword: ''
    };
  } catch (error) {
    ElMessage.error('密码修改失败');
  }
};

const beforeAvatarUpload = (file) => {
  const isImage = file.type.startsWith('image/');
  const isLt2M = file.size / 1024 / 1024 < 2;

  if (!isImage) {
    ElMessage.error('只能上传图片文件！');
    return false;
  }
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 2MB！');
    return false;
  }
  return true;
};

const handleAvatarSuccess = (response) => {
  userInfo.value.avatar = response.url;
  ElMessage.success('头像上传成功');
};

// 初始化用户信息
userInfo.value = { ...authStore.user };
</script>

<style scoped>
.profile-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.avatar-container {
  text-align: center;
  margin-bottom: 20px;
}

.avatar-uploader {
  margin-top: 10px;
}

.profile-card {
  margin-bottom: 20px;
}
</style>
