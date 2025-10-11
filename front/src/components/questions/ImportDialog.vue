<template>
  <el-dialog
    v-model="visible"
    title="批量导入题目"
    width="500px"
    @close="handleClose"
  >
    <div class="import-container">
      <el-upload
        class="upload-demo"
        drag
        action="/api/v1/questions/questions/batch-import"
        accept=".xlsx,.xls"
        :headers="headers"
        :before-upload="beforeUpload"
        :on-success="handleSuccess"
        :on-error="handleError"
        :disabled="uploading"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            请上传Excel文件（.xlsx或.xls格式）
            <el-link type="primary" @click="downloadTemplate">下载模板</el-link>
          </div>
        </template>
      </el-upload>

      <el-progress
        v-if="uploading"
        :percentage="uploadProgress"
        :status="uploadStatus"
      />

      <div v-if="importResult" class="import-result">
        <el-alert
          :title="getResultTitle"
          :type="importResult.success ? 'success' : 'error'"
          :description="getResultDescription"
          show-icon
        />
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed,watch,defineEmits } from 'vue';
import { UploadFilled } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';

const props = defineProps({
  modelValue: Boolean
});

const emit = defineEmits(['update:modelValue', 'success']);

const visible = ref(false);
const uploading = ref(false);
const uploadProgress = ref(0);
const uploadStatus = ref('');
const importResult = ref(null);

// 计算上传请求头
const headers = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem('token')}`
}));

// 计算导入结果标题
const getResultTitle = computed(() => {
  if (!importResult.value) return '';
  return importResult.value.success ? '导入成功' : '导入失败';
});

// 计算导入结果描述
const getResultDescription = computed(() => {
  if (!importResult.value) return '';
  const { total, success, failed } = importResult.value;
  return `共${total}条数据，成功${success}条，失败${failed}条`;
});

// 监听visible变化
watch(() => props.modelValue, (val) => {
  visible.value = val;
});

watch(() => visible.value, (val) => {
  emit('update:modelValue', val);
});

// 上传前检查
const beforeUpload = (file) => {
  const isExcel = file.type === 'application/vnd.ms-excel' || 
                 file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
  if (!isExcel) {
    ElMessage.error('只能上传Excel文件！');
    return false;
  }
  uploading.value = true;
  uploadProgress.value = 0;
  uploadStatus.value = '';
  importResult.value = null;
  return true;
};

// 上传成功处理
const handleSuccess = (response) => {
  uploading.value = false;
  uploadProgress.value = 100;
  uploadStatus.value = 'success';
  importResult.value = response;
  emit('success', response);
};

// 上传失败处理
const handleError = () => {
  uploading.value = false;
  uploadProgress.value = 100;
  uploadStatus.value = 'exception';
  ElMessage.error('导入失败');
};

// 关闭对话框
const handleClose = () => {
  visible.value = false;
  uploading.value = false;
  uploadProgress.value = 0;
  uploadStatus.value = '';
  importResult.value = null;
};

// 下载模板
const downloadTemplate = () => {
  // TODO: 实现模板下载功能
  window.open('/api/v1/questions/template/download');
};
</script>

<style scoped>
.import-container {
  padding: 20px 0;
}

.import-result {
  margin-top: 20px;
}

.el-upload__tip {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
