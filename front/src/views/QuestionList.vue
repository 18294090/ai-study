<template>
  <div class="question-list-container">
    <div class="search-bar">
      <el-form :inline="true" :model="searchForm">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="搜索题目标题或内容" clearable @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="题目类型" style="width: 200px;">
          <el-select v-model="searchForm.type" placeholder="全部类型" clearable>
            <el-option label="单选题" value="SINGLE_CHOICE" />
            <el-option label="多选题" value="MULTIPLE_CHOICE" />
            <el-option label="填空题" value="FILL_IN_BLANK" />
            <el-option label="简答题" value="SHORT_ANSWER" />
          </el-select>
        </el-form-item>
        <el-form-item label="科目" style="width: 200px;">
          <el-select v-model="searchForm.subject_id" placeholder="选择科目" clearable>
            <el-option
              v-for="subject in subjects"
              :key="subject.id"
              :label="subject.name"
              :value="subject.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="success" @click="handleCreate">新建题目</el-button>
        </el-form-item>
      </el-form>
    </div>

    <el-table v-loading="loading" :data="questions" style="width: 100%">
      <el-table-column prop="title" label="标题" min-width="200">
        <template #default="{ row }">
          <el-link type="primary" @click="handleEdit(row)">{{ row.title }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag>{{ formatQuestionType(row.type) }}</el-tag>
        </template>
      </el-table-column>
      <!-- 修复学科列，安全显示名称 -->
      <el-table-column label="科目" width="120">
        <template #default="{ row }">
          {{ row.subject_name || row.subject?.name || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="difficulty" label="难度" width="120">
        <template #default="{ row }">
          <el-rate v-model="row.difficulty" disabled />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button-group>
            <el-button size="small" type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </el-button-group>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-container">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 使用组件自身弹窗：移除外层 el-dialog -->
    <QuestionDialog
      v-model="editDialogVisible"
      :question="editingQuestion"
      @submit="handleSaveSuccess"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import QuestionDialog from '@/components/questions/QuestionDialog.vue';
import http from '../utils/http';
import { useSubjectsStore } from '@/stores/subjects';
import { subjectsApi } from '@/services/subjects';
const store = useSubjectsStore();
// 状态定义
const questions = ref([]);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(10);
const total = ref(0);
const editDialogVisible = ref(false);
const editingQuestion = ref({});
const searchForm = reactive({
  keyword: '',
  type: '',
  subject_id: ''
});

// 从store获取科目列表
const subjects = computed(() => store.subjects);

// 预加载科目数据到store
const preloadSubjects = async () => {
  if (Array.isArray(subjects.value) && subjects.value.length > 0) {
    return;
  }
  // 否则调用后端
  try {
    const res = await subjectsApi.getSubjects('/api/v1/subjects');
    const list = Array.isArray(res.data?.items) ? res.data.items : (Array.isArray(res.data) ? res.data : []);
    store.subjects = list; // 假设store.subjects可写
  } catch (e) {
    store.subjects = [];
    ElMessage.error('获取科目失败');
  }
};

// 获取科目名称
const getSubjectName = (id) => {
  const s = subjects.value.find(x => x.id === id);
  return s?.name || '';
};

// 格式化题目类型
const formatQuestionType = (type) => {
  const types = {
    'single_choice': '单选题',
    'multiple_choice': '多选题',
    'fill_in_blank': '填空题',
    'short_answer': '简答题'
  };
  return types[type] || type;
};

// 加载题目列表（兼容数组或 { items, total }）
const loadQuestions = async () => {
  loading.value = true;
  try {
    const params = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
      ...Object.fromEntries(
        Object.entries(searchForm).filter(([_, value]) => value !== '')
      )
    };
    const resp = await http.get('/questions', { params });
    const items = Array.isArray(resp) ? resp : (resp?.items || resp?.data?.items || []);
    const totalCount = Array.isArray(resp)
      ? (resp.length || 0)
      : (resp?.total ?? resp?.data?.total ?? 0);

    // 映射出学科名称，避免显示ID
    questions.value = items.map(q => ({
      ...q,
      subject_name: q.subject?.name || getSubjectName(q.subject_id) || q.subject_name || '-'
    }));
    total.value = Number(totalCount) || 0;

    if (!items.length) {
      ElMessage.info('没有找到匹配的题目');
    }
  } catch (error) {
    console.error('Failed to load questions:', error);
    const msg = error?.response?.data?.message || error?.message || '加载题目列表失败';
    ElMessage.error(msg);
    questions.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
};

// 搜索处理
const handleSearch = () => {
  currentPage.value = 1;
  loadQuestions();
};

// 重置搜索
const resetSearch = () => {
  Object.assign(searchForm, {
    keyword: '',
    type: '',
    subject_id: ''
  });
  handleSearch();
};

// 解析后端答案JSON（可能是对象或JSON字符串）
const parseAnswerJSON = (answer) => {
  if (!answer) return null;
  if (typeof answer === 'string') {
    try { return JSON.parse(answer); } catch { return null; }
  }
  if (typeof answer === 'object') return answer;
  return null;
};

// 按题型生成表单可编辑字符串
const toAnswerRaw = (item) => {
  const a = parseAnswerJSON(item?.answer);
  const type = item?.type;
  if (!a) return '';
  switch (type) {
    case 'single_choice':
      return a.choice ?? '';
    case 'multiple_choice':
      return Array.isArray(a.choices) ? a.choices.join('') : '';
    case 'fill_in_blank':
      return Array.isArray(a.blanks) ? a.blanks.join('\n') : '';
    case 'short_answer':
      return a.text ?? a.value ?? '';
    default:
      return a.value ?? '';
  }
};

// 编辑处理：携带 answerRaw 给对话框
const handleEdit = (row) => {
  editingQuestion.value = {
    ...row,
    answerRaw: toAnswerRaw(row)
  };
  editDialogVisible.value = true;
};

// 新建题目
const handleCreate = () => {
  editingQuestion.value = {}; // 交给对话框watch填充默认值
  editDialogVisible.value = true;
};

// 删除处理
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除这个题目吗？', '警告', {
      type: 'warning'
    });
    await http.delete(`/questions/${row.id}`);
    ElMessage.success('删除成功');
    loadQuestions();
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to delete question:', error);
      if (error.response) {
        const errorMessage = error.response.data?.message;
        ElMessage.error(typeof errorMessage === 'string' ? errorMessage : '删除失败');
      } else {
        ElMessage.error('删除失败');
      }
    }
  }
};

// 保存成功处理（与 QuestionDialog @submit 对齐）
const handleSaveSuccess = () => {
  editDialogVisible.value = false;
  loadQuestions();
  ElMessage.success('保存成功');
};

// 分页处理
const handleSizeChange = (val) => {
  pageSize.value = val;
  currentPage.value = 1; // 改变每页大小时重置到第一页
  loadQuestions();
};

const handleCurrentChange = (val) => {
  currentPage.value = val;
  loadQuestions();
};

// 初始加载
onMounted(async () => {
  await preloadSubjects();
  loadQuestions();
});
</script>

<style scoped>
.question-list-container {
  padding: 20px;
}

.search-bar {
  margin-bottom: 20px;
  padding: 20px;
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

:deep(.el-table) {
  margin-top: 20px;
}

.el-button-group {
  display: flex;
  gap: 8px;
}
</style>
