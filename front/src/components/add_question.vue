<template>
  <div class="question-form-container">
    <h1>添加题目</h1>
    <el-form ref="questionFormRef" :model="question" :rules="rules" label-width="120px" label-position="right">
      <el-form-item label="标题" prop="title">
        <el-input v-model="question.title" placeholder="请输入标题" />
      </el-form-item>

      <el-form-item label="类型" prop="type">
        <el-select v-model="question.type" placeholder="请选择题目类型">
          <el-option label="单选题" value="single_choice" />
          <el-option label="多选题" value="multiple_choice" />
          <el-option label="填空" value="fill_in_blank" />
          <el-option label="简答题" value="short_answer" />
        </el-select>
      </el-form-item>

      <el-form-item label="科目" prop="subject_id">
        <el-select v-model="question.subject_id" placeholder="请选择科目" filterable>
          <el-option
            v-for="subject in subjects"
            :key="subject.id"
            :label="subject.name"
            :value="subject.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="内容" prop="content">
        <el-input type="textarea" v-model="question.content" placeholder="请输入内容" :rows="4" />
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
          <img v-if="question.picture" :src="getImageUrl(question.picture)" class="avatar" />
          <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
        </el-upload>
      </el-form-item>
      <el-form-item label="选项" v-if="question.type === 'multiple_choice' || question.type === 'single_choice'" prop="options">
        <div v-for="(option, key) in question.options" :key="key" class="option-row">
          <el-input v-model="question.options[key]" :placeholder="'选项 ' + key" />
          <el-button type="danger" @click="removeOption(key)" :icon="Delete" circle />
        </div>
        <el-button type="primary" @click="addOption" :icon="Plus">添加选项</el-button>
      </el-form-item>

      <el-form-item 
        label="答案" 
        prop="answer"
        :rules="[
          { required: true, message: '答案不能为空', trigger: 'blur' },
          { 
            validator: (rule, value, callback) => {
              if (question.type === 'multiple_choice' && value && !value.includes(',')) {
                callback(new Error('多选题答案请用逗号分隔，如: A,B,C'));
              } else {
                callback();
              }
            },
            trigger: 'blur'
          }
        ]"
      >
        <el-input 
          v-model="question.answer" 
          :placeholder="
            question.type === 'single_choice' ? '请输入选项字母，如：A' :
            question.type === 'multiple_choice' ? '请输入选项字母，用逗号分隔，如：A,B,C' :
            '请输入答案'
          "
        />
      </el-form-item>

      <el-form-item label="解析" prop="explanation">
        <el-input type="textarea" v-model="question.explanation" placeholder="请输入解析" :rows="2" />
      </el-form-item>

      <el-form-item label="难度" prop="difficulty">
        <el-rate v-model="question.difficulty" :max="5" />
      </el-form-item>

      <el-form-item label="标签" prop="tags">
        <el-input v-model="tagsInput" placeholder="请输入标签，用逗号分隔" />
      </el-form-item>

      <el-form-item label="知识点" prop="knowledge_points">
        <el-input v-model="knowledgePointsInput" placeholder="请输入知识点，用逗号分隔" />
      </el-form-item>

      <el-form-item label="来源" prop="source">
        <el-input v-model="question.source" placeholder="请输入来源" />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="submitForm">提交</el-button>
        <el-button @click="resetForm">重置</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { useAuthStore } from '../stores/auth';
import http from '../utils/http';
import { ElMessage } from 'element-plus';
import { Plus, Delete } from '@element-plus/icons-vue';

const questionFormRef = ref(null);
const uploadUrl = ref('http://127.0.0.1:8000/api/v1/upload/');

// 获取初始问题数据
function getInitialQuestion() {
  return {
    title: '',
    type: 'single_choice',
    subject_id: '',
    content: '',
    picture: '',
    options: { A: '', B: '', C: '', D: '' },
    answer: '',
    explanation: '',
    difficulty: 3,
    status: 'draft'
  };
}

// 表单数据
const question = reactive(getInitialQuestion());
const tagsInput = ref('');
const knowledgePointsInput = ref('');
const subjects = ref([]);

// 获取科目列表
const fetchSubjects = async () => {
  try {
    const response = await http.get('/api/v1/subjects');
    if (response.code === 0) {
      subjects.value = response.data;
    }
  } catch (error) {
    console.error('获取科目列表失败:', error);
    ElMessage.error('获取科目列表失败');
  }
};

// 上传相关方法
const uploadHeaders = computed(() => {
  const token = localStorage.getItem('token');
  return {
    'Authorization': token ? `Bearer ${token}` : ''
  };
});

const getImageUrl = (path) => {
  if (!path) return '';
  return `${import.meta.env.VITE_API_BASE_URL}/${path}`;
};

const formatAnswer = (answer, type) => {
  if (!answer) return { value: '' };
  
  // 如果已经是对象格式，直接返回
  if (typeof answer === 'object' && answer !== null) {
    return { value: answer.value || answer.choices || '' };
  }

  // 处理字符串类型的答案
  if (typeof answer === 'string') {
    // 处理选择题
    if (['single_choice', 'multiple_choice'].includes(type)) {
      const choices = answer.split(',').map(a => a.trim()).filter(Boolean);
      return { value: type === 'single_choice' ? choices[0] : choices };
    }
    
    // 处理布尔值
    const lowerAnswer = answer.toLowerCase();
    if (lowerAnswer === 'true' || lowerAnswer === 'false') {
      return { value: lowerAnswer === 'true' };
    }
    
    // 其他类型答案
    return { value: answer };
  }
  
  return { value: '' };
}

onMounted(async () => {
  await fetchSubjects();
});


const handleAvatarSuccess = (response, uploadFile) => {
  if (response.code === 0) {
    question.picture = response.data.url;
    ElMessage.success('上传成功');
  } else {
    ElMessage.error(response.msg || '上传失败');
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

const rules = reactive({
  title: [{ required: true, message: '标题不能为空', trigger: 'blur' }],
  type: [{ required: true, message: '请选择题目类型', trigger: 'change' }],
  subject_id: [{ required: true, message: '请选择科目', trigger: 'change' }],
  content: [{ required: true, message: '内容不能为空', trigger: 'blur' }],
  answer: [{ required: true, message: '答案不能为空', trigger: 'blur' }],
  difficulty: [{ required: true, message: '请选择难度', trigger: 'change' }],
  options: [{
    validator: (_, value) => {
      const type = question.type;
      if (['single_choice', 'multiple_choice'].includes(type)) {
        const nonEmptyOptions = Object.values(value || {}).filter(v => v && v.trim() !== '');
        if (nonEmptyOptions.length < 2) {
          return Promise.reject('选择题至少需要两个选项');
        }
      }
      return Promise.resolve();
    },
    trigger: ['blur', 'change']
  }]
});

const addOption = () => {
  const optionKeys = Object.keys(question.options);
  const nextOption = String.fromCharCode(65 + optionKeys.length);
  question.options[nextOption] = '';
};

const removeOption = (key) => {
  delete question.options[key];
};

const submitForm = async () => {
  if (!questionFormRef.value) {
    ElMessage.warning('表单未准备就绪，请稍后重试');
    return;
  }
  
  try {
    // 表单验证
    await questionFormRef.value.validate();
    
    // 数据预处理
    const formattedAnswer = formatAnswer(question.answer, question.type);
    const tags = tagsInput.value.split(',').map(tag => tag.trim()).filter(Boolean);
    const knowledge_points = knowledgePointsInput.value.split(',').map(kp => kp.trim()).filter(Boolean);
    
    // 构建提交数据
    const data = {
      ...question,
      answer: formattedAnswer,
      tags,
      knowledge_points,
      options: ['single_choice', 'multiple_choice'].includes(question.type) ? question.options : null
    };

    // 发送请求
    const response = await http.post('/api/v1/questions', data);
    if (response.code === 0) {
      ElMessage.success('题目添加成功！');
      resetForm();
    } else {
      throw new Error(response.msg || '添加题目失败');
    }
  } catch (error) {
    console.error('添加题目失败:', error);
    
    // 错误处理
    const errorMessage = error.response?.data?.detail || 
                        error.message || 
                        '添加题目失败，请检查输入数据并重试';
    ElMessage.error(errorMessage);
  }
};

const resetForm = () => {
  if (!questionFormRef.value) return;
  questionFormRef.value.resetFields();
  Object.assign(question, getInitialQuestion());
  tagsInput.value = '';
  knowledgePointsInput.value = '';
};
</script>

<style scoped>
.question-form-container {
  max-width: 800px;
  margin: 20px auto;
  padding: 20px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

h1 {
  text-align: center;
  margin-bottom: 20px;
}

.option-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  width: 100%;
}

.option-row .el-input {
  flex-grow: 1;
}

.el-form-item {
  margin-bottom: 22px;
}

.el-select {
  width: 100%;
}

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
</style>
