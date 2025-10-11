<template>
  <el-dialog
    :title="isEdit ? '编辑学科' : '新建学科'"
    v-model="dialogVisible"
    width="500px"
    destroy-on-close
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-form-item label="学科名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入学科名称" />
      </el-form-item>
      <el-form-item label="描述" prop="description">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="4"
          placeholder="请输入学科描述"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { useSubjectsStore } from '@/stores/subjects';

const props = defineProps({
  modelValue: Boolean,
  subject: Object
});

const emit = defineEmits(['update:modelValue', 'success']);

const subjectsStore = useSubjectsStore();
const formRef = ref(null);
const loading = ref(false);
const form = ref({
  id: null,
  name: '',
  description: ''
});

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
});

const isEdit = computed(() => !!form.value.id);

const rules = {
  name: [
    { required: true, message: '请输入学科名称', trigger: 'blur' },
    { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
  ]
};

watch(() => props.subject, (val) => {
  if (val) {
    form.value = { ...val };
  } else {
    form.value = { id: null, name: '', description: '' };
  }
}, { immediate: true });

const handleSubmit = async () => {
  if (!formRef.value) return;
  
  try {
    await formRef.value.validate();
    loading.value = true;
    
    if (isEdit.value) {
      await subjectsStore.updateSubject(form.value.id, form.value);
      ElMessage.success('更新成功');
    } else {
      await subjectsStore.createSubject(form.value);
      ElMessage.success('创建成功');
    }
    
    emit('success');
    dialogVisible.value = false;
  } catch (error) {
    ElMessage.error(error.message || '操作失败');
  } finally {
    loading.value = false;
  }
};
</script>
