<template>
  <el-dialog
    v-if="visible"
    :title="form.id ? '编辑科目' : '新增科目'"
    :model-value="visible"
    @update:model-value="handleVisibleChange"
    width="500px"
    destroy-on-close
    @closed="handleDialogClosed"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
      <el-form-item label="名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入科目名称" />
      </el-form-item>
      <el-form-item label="描述" prop="description">
        <el-input
          v-model="form.description"
          type="textarea"
          placeholder="请输入科目描述"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="updateVisible(false)">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSave">
        确定
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { ElMessage } from 'element-plus';
import { subjectsApi } from '@/services/subjects';

const props = defineProps({
  visible: Boolean,
  defaultValues: {
    type: Object,
    default: () => ({})
  }
});

const emit = defineEmits(['update:visible', 'success']);

const formRef = ref(null);
const loading = ref(false);
const form = ref({
  id: null,
  name: '',
  description: ''
});

const handleVisibleChange = async (val) => {
  emit('update:visible', val);
  if (!val) {
    await nextTick();
    form.value = {
      id: null,
      name: '',
      description: ''
    };
  }
};

const handleDialogClosed = () => {
  formRef.value?.resetFields();
  emit('update:visible', false);
};

// 初始化时确保表单已经挂载
onMounted(() => {
  if (props.visible) {
    nextTick(() => {
      if (props.defaultValues) {
        form.value = { ...props.defaultValues };
      }
    });
  }
});

// 清理工作
onBeforeUnmount(() => {
  form.value = {
    id: null,
    name: '',
    description: ''
  };
});

const updateVisible = (val) => {
  emit('update:visible', val);
  if (!val) {
    nextTick(() => {
      resetForm();
    });
  }
};

watch(() => props.visible, async (val) => {
  if (val) {
    await nextTick();
    if (props.defaultValues) {
      form.value = { ...props.defaultValues };
    } else {
      resetForm();
    }
  }
},{ immediate: true });

const resetForm = () => {
  if (formRef.value) {
    formRef.value.resetFields();
  }
  form.value = {
    id: null,
    name: '',
    description: ''
  };
};

const handleSave = async () => {
  if (!formRef.value) return;
  
  try {
    const valid = await formRef.value.validate();
    if (!valid) return;
    
    loading.value = true;
    const data = { ...form.value };
    
    if (data.id) {
      await subjectsApi.updateSubject(data.id, data);
      ElMessage.success('修改成功');
    } else {
      await subjectsApi.createSubject(data);
      ElMessage.success('创建成功');
    }
    
    emit('success');
    handleVisibleChange(false);
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败');
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.el-dialog__body {
  padding-top: 20px;
}
</style>