<template>
  <el-card class="profile-card">
    <template #header>
      <div class="card-header">
        <h2>个人信息</h2>
      </div>
    </template>
    
    <el-form
      v-if="authStore.user"
      ref="formRef"
      :model="formData"
      :rules="rules"
      label-width="80px"
    >
      <el-form-item label="用户名">
        <el-input v-model="formData.username" disabled></el-input>
      </el-form-item>
      
      <el-form-item label="全名" prop="full_name">
        <el-input v-model="formData.full_name" placeholder="请输入您的全名"></el-input>
      </el-form-item>
      
      <el-form-item label="邮箱" prop="email">
        <el-input v-model="formData.email" placeholder="请输入您的邮箱"></el-input>
      </el-form-item>
      
      <el-form-item label="角色">
        <el-tag :type="roleTypeMap[formData.role]">
          {{ roleNameMap[formData.role] || formData.role }}
        </el-tag>
      </el-form-item>

      <el-form-item v-if="formData.role === 'teacher'" label="任教科目" prop="subjects">
        <el-select
          v-model="formData.subjects"
          multiple
          filterable
          placeholder="请选择您的任教科目"
          style="width: 100%"
          :multiple-limit="4"
        >
          <el-option
            v-for="item in availableSubjects"
            :key="item.id"
            :label="item.name"
            :value="item"
          />
        </el-select>
        <div class="form-tip">最多可选择4个科目</div>
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="handleUpdate" :loading="loading">
          更新信息
        </el-button>
        <el-button @click="resetForm">重置</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '../stores/auth';
import { ElMessage } from 'element-plus';
import http from '../utils/http';

const authStore = useAuthStore();
const formRef = ref(null);
const loading = ref(false);
const formData = ref({
  username: '',
  full_name: '',
  email: '',
  role: '',
  subjects: []
});

// 角色显示映射
const roleNameMap = {
  'student': '学生',
  'teacher': '教师',
  'admin': '管理员'
};

const roleTypeMap = {
  'student': 'info',
  'teacher': 'success',
  'admin': 'danger'
};

// 可用科目列表
const availableSubjects = ref([
  { id: 'math', name: '数学' },
  { id: 'physics', name: '物理' },
  { id: 'chemistry', name: '化学' },
  { id: 'biology', name: '生物' },
  { id: 'chinese', name: '语文' },
  { id: 'english', name: '英语' },
  { id: 'history', name: '历史' },
  { id: 'geography', name: '地理' },
  { id: 'politics', name: '政治' }
]);

// 表单验证规则
const rules = {
  full_name: [
    { required: true, message: '请输入您的全名', trigger: 'blur' },
    { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱地址', trigger: ['blur', 'change'] }
  ],
  subjects: [
    { 
      required: true, 
      message: '请至少选择一个任教科目', 
      trigger: 'change',
      validator: (rule, value, callback) => {
        if (formData.value.role === 'teacher' && (!value || value.length === 0)) {
          callback(new Error('请至少选择一个任教科目'));
        } else {
          callback();
        }
      }
    }
  ]
};

// 加载可用科目列表
const fetchAvailableSubjects = async () => {
  try {
    const response = await http.get('/api/v1/subjects/available');
    if (response.code === 0) {
      availableSubjects.value = response.data;
    }
  } catch (error) {
    console.error('获取科目列表失败:', error);
    ElMessage.error('获取科目列表失败');
  }
};

onMounted(async () => {
  if (authStore.user) {
    // 合并用户数据
    formData.value = { 
      ...formData.value,
      ...authStore.user,
      subjects: authStore.user.subjects || []
    };
  }
  // 加载科目列表
  await fetchAvailableSubjects();
});

const handleUpdate = async () => {
  if (!formRef.value) return;

  try {
    await formRef.value.validate();
    loading.value = true;
    
    const updateData = {
      full_name: formData.value.full_name,
      email: formData.value.email,
      subjects: formData.value.subjects
    };

    await authStore.updateProfile(formData.value.id, updateData);
    ElMessage.success('个人信息更新成功！');
  } catch (error) {
    console.error('Update failed:', error);
    if (error.response?.data?.detail) {
      ElMessage.error(error.response.data.detail);
    } else if (error.message) {
      ElMessage.error(error.message);
    } else {
      ElMessage.error('信息更新失败');
    }
  } finally {
    loading.value = false;
  }
};

const resetForm = () => {
  if (formRef.value) {
    formRef.value.resetFields();
    // 重新加载用户数据
    if (authStore.user) {
      formData.value = { 
        ...formData.value,
        ...authStore.user,
        subjects: authStore.user.subjects || []
      };
    }
  }
};
</script>

<style scoped>
.profile-card {
  max-width: 600px;
  margin: 50px auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.2;
}
</style>
