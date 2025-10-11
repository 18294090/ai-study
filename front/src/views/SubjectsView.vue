<template>
  <div class="subjects-container">
    <el-card class="page-header">
      <el-row :gutter="20">
        <el-col :span="16">
          <h2>我的学科管理</h2>
          <p class="text-secondary">管理您的学科和相关知识点</p>
        </el-col>
        <el-col :span="8" class="text-right">
          <el-button type="primary" @click="showCreateDialog" :icon="Plus">
            新建学科
          </el-button>
        </el-col>
      </el-row>
    </el-card>
    <div class="subjects-list">
      <el-row :gutter="20">
        <el-col v-for="subject in subjects" :key="subject.id" :xs="24" :sm="12" :md="8" :lg="6" class="mb-4">
          <el-card class="subject-card" shadow="hover" @click="viewSubject(subject.id)">
            <div class="subject-card-header">
              <h3>{{ subject.name }}</h3>
              <div class="actions">
                <el-button type="primary" size="small" @click.stop="() => showUploadDocumentDialog(subject.id)" :icon="Upload">上传学科文档</el-button>
                <el-dropdown trigger="click" @click.stop>
                  <el-button type="text" :icon="MoreFilled" />
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click.stop="viewSubject(subject.id)" :icon="View">查看详情</el-dropdown-item>
                      <el-dropdown-item @click.stop="editSubject(subject)" :icon="Edit">编辑</el-dropdown-item>
                      <el-dropdown-item @click.stop="deleteSubject(subject.id)" :icon="Delete" divided>删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </div>
            <p class="subject-description">{{ subject.description || '暂无描述' }}</p>
            <div class="subject-stats">
              <el-tag size="small">{{ subject.knowledge_points_count || 0 }} 个知识点</el-tag>
              <el-tag size="small">{{ subject.documents_count || 0 }} 个文档</el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
    <!-- 空状态提示 -->
    <el-empty v-if="!loading && subjects.length === 0" description="暂无学科，点击新建学科按钮创建学科">
      <el-button type="primary" @click="showCreateDialog">新建学科</el-button>
    </el-empty>
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="3" animated />
    </div>
    <!-- 新建/编辑学科对话框 -->
    <subject-dialog 
      v-model="dialogVisible" 
      :subject="currentSubject"
      @success="handleSuccess"
    />

    <!-- 上传文档对话框 -->
    <upload-document 
      v-model="uploadVisible" 
      :subject-id="currentSubjectId"
      @success="handleUploadSuccess"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useSubjectsStore } from '@/stores/subjects';
import { ElMessage, ElMessageBox } from 'element-plus';
import SubjectDialog from '@/components/SubjectDialog.vue';
import UploadDocument from '@/components/UploadDocument.vue';
import { Plus, Edit, Delete, View, MoreFilled, Upload } from '@element-plus/icons-vue';
const router = useRouter();
const store = useSubjectsStore();
// 获取学科列表
const subjects = computed(() => store.subjects);
const loading = ref(false);
const dialogVisible = ref(false);
const currentSubject = ref(null);
const uploadVisible = ref(false);
const currentSubjectId = ref(null);
// 显示创建对话框
const showCreateDialog = () => {
  currentSubject.value = null;
  dialogVisible.value = true;
};

// 编辑学科
const editSubject = (subject) => {
  currentSubject.value = { ...subject };
  dialogVisible.value = true;
};

// 查看学科详情
const viewSubject = (id) => {
  router.push(`/subjects/${id}`);
};

// 删除学科
const deleteSubject = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该学科吗？这将同时删除所有相关的知识点。', '提示', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    });    
    loading.value = true;
    await store.deleteSubject(id);
    ElMessage.success('删除成功');
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + (error.message || '未知错误'));
    }
  } finally {
    loading.value = false;
  }
};

// 上传文档
const showUploadDocumentDialog = (subjectId) => {
  currentSubjectId.value = subjectId;
  uploadVisible.value = true;
};

// 处理学科创建/编辑成功
const handleSuccess = () => {
  fetchSubjects();
};

// 处理上传成功
const handleUploadSuccess = () => {
  uploadVisible.value = false;
  // 可选：刷新学科列表或文档列表
};

// 获取学科列表
const fetchSubjects = async () => {
  loading.value = true;
  try {
    await store.fetchSubjects();
  } catch (error) {
    ElMessage.error('获取学科列表失败: ' + (error.message || '未知错误'));
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  fetchSubjects();
});
</script>

<style scoped>
.subjects-container {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
  margin-bottom: 20px;
}

.text-secondary {
  color: #909399;
  margin-top: 8px;
}

.subject-card {
  height: 100%;
  cursor: pointer;
  transition: all 0.3s;
}

.subject-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 20px rgba(0,0,0,0.1);
}

.subject-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start
}

.subject-card-header h3 {
  margin: 0;
  font-size: 18px;
  overflow: hidden; 
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.subject-description {
  margin: 10px 0;
  color: #606266;
  height: 40px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;;}

.subject-stats {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
</style>

