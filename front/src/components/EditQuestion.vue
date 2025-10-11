<template>
  <el-form ref="questionFormRef" :model="questionForm" :rules="rules" label-width="120px" label-position="right">
    <el-form-item label="标题" prop="title">
      <el-input v-model="questionForm.title" placeholder="请输入标题" />
    </el-form-item>

    <el-form-item label="类型" prop="type">
      <el-select v-model="questionForm.type" placeholder="请选择题目类型">
        <el-option label="单选题" value="single_choice" />
        <el-option label="多选题" value="multiple_choice" />
        <el-option label="填空题" value="fill_in_blank" />
        <el-option label="简答题" value="short_answer" />
      </el-select>
    </el-form-item>

    <el-form-item label="科目" prop="subject">
      <el-input v-model="questionForm.subject" placeholder="请输入科目" />
    </el-form-item>

    <el-form-item label="内容" prop="content">
      <el-input type="textarea" v-model="questionForm.content" placeholder="请输入内容" :rows="4" />
    </el-form-item>

    <el-form-item label="图片" prop="picture">
      <el-upload
        class="avatar-uploader"
        :action="uploadUrl"
        :on-success="handleAvatarSuccess"
        :on-error="handleAvatarError"
        :before-upload="beforeAvatarUpload"
        :headers="uploadHeaders"
        :show-file-list="true"
      >
        <img v-if="questionForm.picture" :src="getImageUrl(questionForm.picture)" class="avatar" />
        <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
      </el-upload>
    </el-form-item>

    <el-form-item label="选项" v-if="['single_choice', 'multiple_choice'].includes(questionForm.type)" prop="options">
      <div v-if="questionForm.type === 'single_choice' && isBoolean(questionForm.answer)" class="option-row">
        <el-radio-group v-model="questionForm.answer">
          <el-radio :label="true">对</el-radio>
          <el-radio :label="false">错</el-radio>
        </el-radio-group>
      </div>
      <template v-else>
        <div v-for="(option, key) in questionForm.options" :key="key" class="option-row">
          <el-input v-model="questionForm.options[key]" :placeholder="'选项 ' + key" />
          <el-button type="danger" @click="removeOption(key)" :icon="Delete" circle />
        </div>
        <el-button type="primary" @click="addOption" :icon="Plus">添加选项</el-button>
      </template>
    </el-form-item>

    <el-form-item label="答案" prop="answer">
      <el-input v-model="questionForm.answer" placeholder="请输入答案" />
    </el-form-item>

    <el-form-item label="解析" prop="explanation">
      <el-input type="textarea" v-model="questionForm.explanation" placeholder="请输入解析" :rows="2" />
    </el-form-item>

    <el-form-item label="难度" prop="difficulty">
      <el-rate v-model="questionForm.difficulty" :max="5" />
    </el-form-item>

    <el-form-item label="标签" prop="tags">
      <el-select
        v-model="questionForm.tags"
        multiple
        filterable
        allow-create
        default-first-option
        placeholder="请输入标签"
      >
        <el-option v-for="tag in tags" :key="tag" :label="tag" :value="tag" />
      </el-select>
    </el-form-item>

    <el-form-item label="知识点" prop="knowledge_points">
      <el-select
        v-model="questionForm.knowledge_points"
        multiple
        filterable
        allow-create
        default-first-option
        placeholder="请输入知识点"
      >
        <el-option
          v-for="point in knowledgePoints"
          :key="point"
          :label="point"
          :value="point"
        />
      </el-select>
    </el-form-item>

    <el-form-item label="来源" prop="source">
      <el-input v-model="questionForm.source" placeholder="请输入来源" />
    </el-form-item>

    <el-form-item>
      <el-button type="primary" @click="handleSubmit">保存</el-button>
      <el-button @click="handleCancel">取消</el-button>
    </el-form-item>
  </el-form>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { Plus, Delete } from '@element-plus/icons-vue';
import http from '../utils/http';

const props = defineProps({
  question: {
    type: Object,
    required: true
  }
});

const emit = defineEmits(['save-success', 'cancel']);

// 表单引用
const questionFormRef = ref(null);
const uploadUrl = ref(import.meta.env.VITE_API_BASE_URL + '/api/v1/upload');
const tags = ref([]);
const knowledgePoints = ref([]);

// 表单数据
const questionForm = reactive({
  ...getInitialQuestion(),
  ...props.question
});

// 上传相关
const uploadHeaders = {
  // 如果需要认证，在这里添加token
  // 'Authorization': `Bearer ${localStorage.getItem('token')}`
};

const getImageUrl = (path) => {
  if (!path) return '';
  return `${import.meta.env.VITE_API_BASE_URL}/${path}`;
};

// 检查是否为布尔值（判断题答案）
const isBoolean = (value) => {
  return typeof value === 'boolean' || (typeof value === 'object' && value?.value === true || value?.value === false);
};

// 获取初始问题数据
function getInitialQuestion() {
  return {
    title: '',
    type: 'single_choice',
    subject: '',
    content: '',
    picture: '',
    options: { A: '', B: '', C: '', D: '' },
    answer: '',  // 使用简单字符串，在提交时会转换为正确的格式
    explanation: '',
    difficulty: 3,
    tags: [],
    knowledge_points: [],
    source: '',
    status: 'DRAFT'
  };
}

// 文件上传处理
const handleAvatarSuccess = (response) => {
  if (response.code === 0) {
    questionForm.picture = response.data.url;
    ElMessage.success('上传成功');
  } else {
    const errorMsg = typeof response.msg === 'string' ? response.msg : '上传失败';
    ElMessage.error(errorMsg);
  }
};

const handleAvatarError = (error) => {
  console.error('上传错误:', error);
  ElMessage.error('图片上传失败，请重试');
};

const beforeAvatarUpload = (file) => {
  const isJpgOrPng = ['image/jpeg', 'image/png', 'image/gif'].includes(file.type);
  const isLt5M = file.size / 1024 / 1024 < 5;

  if (!isJpgOrPng) {
    ElMessage.error('上传图片只能是 JPG/PNG/GIF 格式!');
    return false;
  }
  if (!isLt5M) {
    ElMessage.error('上传图片大小不能超过 5MB!');
    return false;
  }
  return true;
};

// 选项处理
const addOption = () => {
  const optionKeys = Object.keys(questionForm.options);
  const nextOption = String.fromCharCode(65 + optionKeys.length);
  questionForm.options[nextOption] = '';
};

const removeOption = (key) => {
  delete questionForm.options[key];
};

// 表单验证规则
const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  type: [{ required: true, message: '请选择题目类型', trigger: 'change' }],
  subject: [{ required: true, message: '请输入科目', trigger: 'blur' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
  answer: [{ 
    required: true, 
    message: '请输入答案', 
    trigger: 'blur',
    validator: (_, value) => {
      if (!value && value !== false) return Promise.reject('请输入答案');
      if (typeof value === 'string' && value.trim() === '') return Promise.reject('请输入答案');
      return Promise.resolve();
    }
  }],
  difficulty: [{ required: true, message: '请选择难度', trigger: 'change' }],
  options: [{
    validator: (_, value) => {
      const type = questionForm.type;
      if (['single_choice', 'multiple_choice'].includes(type)) {
        // 检查是否至少有两个选项
        const nonEmptyOptions = Object.values(value || {}).filter(v => v && v.trim() !== '');
        if (nonEmptyOptions.length < 2) {
          return Promise.reject('选择题至少需要两个选项');
        }
      }
      return Promise.resolve();
    },
    trigger: ['blur', 'change']
  }]
};

// 提交处理
const handleSubmit = async () => {
  if (!questionFormRef.value) return;
  
  try {
    await questionFormRef.value.validate();
    
    // 处理答案格式
    let formattedAnswer;
    if (typeof questionForm.answer === 'string') {
      if (['single_choice', 'multiple_choice'].includes(questionForm.type)) {
        // 多选题答案可能是多个选项，用逗号分隔
        const choices = questionForm.answer.split(',').map(a => a.trim()).filter(a => a);
        formattedAnswer = {
          value: questionForm.type === 'single_choice' ? choices[0] : choices
        };
      } else if (questionForm.type === 'true_false') {
        formattedAnswer = {
          value: questionForm.answer.toLowerCase() === 'true'
        };
      } else {
        formattedAnswer = { value: questionForm.answer };
      }
    } else if (typeof questionForm.answer === 'object' && questionForm.answer !== null) {
      formattedAnswer = {
        value: questionForm.answer.value || questionForm.answer.choices || ''
      };
    } else {
      formattedAnswer = { value: '' };
    }

    // 处理选项格式
    let formattedOptions = null;
    if (['single_choice', 'multiple_choice'].includes(questionForm.type)) {
      formattedOptions = Object.fromEntries(
        Object.entries(questionForm.options || {})
          .filter(([_, value]) => value && value.trim() !== '')
      );
    }

    const data = {
      ...questionForm,
      options: formattedOptions,
      answer: formattedAnswer
    };

    const url = data.id 
      ? `/api/v1/questions/${data.id}`
      : '/api/v1/questions';
    
    const method = data.id ? 'put' : 'post';
    
    const response = await http[method](url, data);
    if (response.code === 0) {
      ElMessage.success('保存成功');
      emit('save-success');
    }
  } catch (error) {
    // 错误已经在 http 拦截器中处理，这里只需要记录日志
    console.error('保存失败:', error);
  }
};

const handleCancel = () => {
  emit('cancel');
};

// 加载标签和知识点列表
const loadTagsAndKnowledgePoints = async () => {
  try {
    const [tagsResponse, kpResponse] = await Promise.all([
      http.get('/api/v1/questions/tags'),
      http.get('/api/v1/questions/knowledge-points')
    ]);
    tags.value = tagsResponse.data.data;
    knowledgePoints.value = kpResponse.data.data;
  } catch (error) {
    console.error('Failed to load tags or knowledge points:', error);
  }
};

onMounted(() => {
  loadTagsAndKnowledgePoints();
});
</script>

<style scoped>
.avatar-uploader {
  border: 1px dashed var(--el-border-color);
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: var(--el-transition-duration-fast);
}

.avatar-uploader:hover {
  border-color: var(--el-color-primary);
}

.avatar-uploader-icon {
  font-size: 28px;
  color: #8c939d;
  width: 178px;
  height: 178px;
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar {
  width: 178px;
  height: 178px;
  display: block;
  object-fit: cover;
}

.option-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.option-row .el-input {
  flex-grow: 1;
}

:deep(.el-select) {
  width: 100%;
}
</style>
