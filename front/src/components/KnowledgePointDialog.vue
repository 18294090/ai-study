<template>
  <el-dialog
    :title="isEdit ? '编辑知识点' : '添加知识点'"
    v-model="dialogVisible"
    width="500px"
    destroy-on-close
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-form-item label="知识点名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入知识点名称" />
      </el-form-item>
      <el-form-item label="描述" prop="description">
        <el-input
          v-model="form.description"
          type="textarea"
          rows="4"
          placeholder="请输入知识点描述"
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
import { useKnowledgePointsStore } from '@/stores/knowledgePoints';

const props = defineProps({
  modelValue: Boolean,
  subjectId: {
    type: [String, Number],
    required: true
  },
  knowledgePoint: Object
});

const emit = defineEmits(['update:modelValue', 'success']);

const knowledgePointsStore = useKnowledgePointsStore();
const formRef = ref(null);
const loading = ref(false);
const form = ref({
  id: null,
  subject_id: null,
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
    { required: true, message: '请输入知识点名称', trigger: 'blur' },
    { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
  ]
};

watch(() => props.knowledgePoint, (val) => {
  if (val) {
    form.value = { ...val };
  } else {
    form.value = { 
      id: null, 
      subject_id: props.subjectId,
      name: '', 
      description: '' 
    };
  }
}, { immediate: true });

const handleSubmit = async () => {
  if (!formRef.value) return;
  
  try {
    await formRef.value.validate();
    loading.value = true;
    
    // 确保设置了subject_id
    form.value.subject_id = props.subjectId;
    
    if (isEdit.value) {
      await knowledgePointsStore.updateKnowledgePoint(form.value.id, form.value);
      ElMessage.success('更新成功');
    } else {
      await knowledgePointsStore.createKnowledgePoint(form.value);
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
