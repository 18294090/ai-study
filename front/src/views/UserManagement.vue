<template>
  <div>
    <el-button type="primary" @click="handleAdd" style="margin-bottom: 20px;">添加用户</el-button>
    <el-table :data="userStore.users" style="width: 100%">
      <el-table-column prop="id" label="ID" width="180"></el-table-column>
      <el-table-column prop="username" label="用户名" width="180"></el-table-column>
      <el-table-column prop="full_name" label="全名"></el-table-column>
      <el-table-column prop="email" label="邮箱"></el-table-column>
      <el-table-column label="操作">
        <template #default="scope">
          <el-button size="small" @click="handleEdit(scope.row)"
            >编辑</el-button
          >
          <el-button size="small" type="danger" @click="handleDelete(scope.row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="dialogTitle">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="formData.username"></el-input>
        </el-form-item>
        <el-form-item label="全名" prop="full_name">
          <el-input v-model="formData.full_name"></el-input>
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="formData.email"></el-input>
        </el-form-item>
        <el-form-item v-if="!isEdit" label="密码" prop="password">
          <el-input v-model="formData.password" type="password"></el-input>
        </el-form-item>
         <el-form-item label="角色" prop="role">
          <el-select v-model="formData.role" placeholder="请选择角色">
            <el-option label="学生" value="student"></el-option>
            <el-option label="教师" value="teacher"></el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, reactive } from 'vue';
import { useUserStore } from '../stores/users';
import { ElMessageBox, ElMessage } from 'element-plus';

const userStore = useUserStore();

onMounted(() => {
  userStore.fetchUsers();
});

const dialogVisible = ref(false);
const isEdit = ref(false);
const formRef = ref(null);
const formData = ref({});

const dialogTitle = computed(() => (isEdit.value ? '编辑用户' : '添加用户'));

const formRules = reactive({
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  full_name: [{ required: true, message: '请输入全名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: ['blur', 'change'] },
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
});

const handleAdd = () => {
  isEdit.value = false;
  formData.value = {
    role: 'student' // 默认角色
  };
  dialogVisible.value = true;
  formRef.value?.clearValidate();
};

const handleEdit = (user) => {
  isEdit.value = true;
  formData.value = { ...user };
  dialogVisible.value = true;
  formRef.value?.clearValidate();
};

const handleDelete = async (userId) => {
  try {
    await ElMessageBox.confirm('您确定要删除该用户吗？此操作不可撤销。', '警告', {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning',
    });
    await userStore.deleteUser(userId);
    ElMessage.success('用户删除成功！');
  } catch (error) {
    // 如果用户点击取消，ElMessageBox.confirm 会 reject 一个 'cancel' 字符串
    if (error !== 'cancel') {
      ElMessage.error('删除用户失败。');
    }
  }
};

const handleSubmit = async () => {
  if (!formRef.value) return;
  await formRef.value.validate(async (valid) => {
    if (valid) {
      try {
        if (isEdit.value) {
          await userStore.updateUser(formData.value.id, formData.value);
          ElMessage.success('用户更新成功！');
        } else {
          await userStore.addUser(formData.value);
          ElMessage.success('用户添加成功！');
        }
        dialogVisible.value = false;
      } catch (error) {
        console.error('Operation failed:', error);
        ElMessage.error(error.response?.data?.detail || '操作失败，请稍后重试。');
      }
    }
  });
};
</script>

<style scoped>
</style>