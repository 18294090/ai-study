<template>
  <div>
    <el-dialog v-model="dialogVisible" title="上传文档" width="500px" :append-to-body="true">
      <el-upload
        ref="uploadRef"
        :action="uploadUrl"
        :headers="uploadHeaders"
        :on-success="handleUploadSuccess"
        :on-error="handleUploadError"
        :before-upload="beforeUpload"
        :show-file-list="false"
        accept=".pdf,.txt"
      >
        <el-button type="primary">选择文件</el-button>
      </el-upload>
      <el-form v-if="form.file_path" :model="form" label-width="100px">
        <el-form-item label="标题">
          <el-input v-model="form.title" placeholder="请输入文档标题" />
        </el-form-item>
        <el-form-item label="学科ID">
          <el-input v-model="form.subject_id" :disabled="true" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitDocument" :loading="submitting" :disabled="!form.file_path">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import axios from 'axios';
const uploadUrl = '/api/v1/upload';
const uploadHeaders = { Authorization: `Bearer ${localStorage.getItem('token')}` };
const form = ref({ title: '', subject_id: null, file_path: '', book_id: '' });
const uploadRef = ref();
const submitting = ref(false);
const props = defineProps({
  modelValue: Boolean, 
  subjectId: Number
});
const emit = defineEmits(['update:modelValue', 'success']);
const dialogVisible = ref(false);

watch(() => props.modelValue, (val) => {
  dialogVisible.value = val;
  if (val && props.subjectId) {
    form.value.subject_id = props.subjectId;
  } else {
    form.value.subject_id = null;  // 确保为 null 而非 undefined
  }
});

watch(dialogVisible, (val) => {
  emit('update:modelValue', val);
});

const beforeUpload = (file) => {
  // 验证文件类型
  if (!['application/pdf', 'text/plain'].includes(file.type)) {
    ElMessage.error('仅支持 PDF 或 TXT 文件');
    return false;
  }
  return true;
};

const handleUploadSuccess = (response) => {
  form.value.file_path = response.url;
};

const handleUploadError = () => {
  ElMessage.error('上传失败');
};

const submitDocument = async () => {
  submitting.value = true;
  try {
    // 创建 Book
    const createResponse = await axios.post('/api/v1/books/create', {
      title: form.value.title,
      subject_id: form.value.subject_id
    }, { headers: uploadHeaders });
    form.value.book_id = createResponse.data.id;
    // 处理文档
    await axios.post('/api/v1/books/process', {
      file_path: form.value.file_path,
      title: form.value.title,
      book_id: form.value.book_id
    }, { headers: uploadHeaders });
    ElMessage.success('文档处理成功');
    dialogVisible.value = false;
    emit('success');
  } catch (error) {
    ElMessage.error('处理失败: ' + error.message);
  } finally {
    submitting.value = false;
  }
};
</script>