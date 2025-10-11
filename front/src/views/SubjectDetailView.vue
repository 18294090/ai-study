<template>
  <div class="subject-detail">
    <el-card class="page-header">
      <el-page-header @back="goBack">
        <template #content>
          <div class="page-title">
            <h2>{{ subject.name }}</h2>
            <el-button 
              type="primary" 
              size="small" 
              :icon="Edit" 
              @click="editSubject"
              class="ml-4"
            >
              编辑学科
            </el-button>
          </div>
        </template>
      </el-page-header>
      <p class="subject-description">{{ subject.description || '暂无描述' }}</p>
    </el-card>

    <el-card class="content-section">
      <div class="section-header">
        <h3>知识点管理</h3>
        <el-button type="primary" :icon="Plus" @click="showCreateKnowledgePoint">
          添加知识点
        </el-button>
      </div>

      <!-- 知识点列表 -->
      <el-table v-loading="loading" :data="knowledgePoints" border>
        <el-table-column prop="name" label="知识点名称" min-width="180" />
        <el-table-column prop="description" label="描述" min-width="280" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button-group>
              <el-button size="small" type="primary" :icon="Edit" @click="editKnowledgePoint(row)">
                编辑
              </el-button>
              <el-button size="small" type="danger" :icon="Delete" @click="deleteKnowledgePoint(row.id)">
                删除
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>

      <!-- 空状态提示 -->
      <el-empty 
        v-if="!loading && knowledgePoints.length === 0" 
        description="暂无知识点，点击 '添加知识点'按钮创建"
      >
        <el-button type="primary" @click="showCreateKnowledgePoint">添加知识点</el-button>
      </el-empty>
    </el-card>

    <!-- 知识点对话框 -->
    <knowledge-point-dialog
      v-model="knowledgePointDialog"
      :subject-id="subjectId"
      :knowledge-point="currentKnowledgePoint"
      @success="handleKnowledgePointSuccess"
    />

    <!-- 学科编辑对话框 -->
    <subject-dialog 
      v-model="subjectDialog" 
      :subject="subject"
      @success="handleSubjectSuccess"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Plus, Edit, Delete } from '@element-plus/icons-vue';
import { useSubjectsStore } from '@/stores/subjects';
import { useKnowledgePointsStore } from '@/stores/knowledgePoints';
import SubjectDialog from '@/components/SubjectDialog.vue';
import KnowledgePointDialog from '@/components/KnowledgePointDialog.vue';

const route = useRoute();
const router = useRouter();
const subjectsStore = useSubjectsStore();
const knowledgePointsStore = useKnowledgePointsStore();

const subjectId = computed(() => route.params.id);
const subject = ref({});
const knowledgePoints = ref([]);
const loading = ref(false);
const knowledgePointDialog = ref(false);
const subjectDialog = ref(false);
const currentKnowledgePoint = ref(null);

// 返回学科列表页面
const goBack = () => router.push('/subjects');

// 编辑学科
const editSubject = () => {
  subjectDialog.value = true;
};

// 创建知识点
const showCreateKnowledgePoint = () => {
  currentKnowledgePoint.value = null;
  knowledgePointDialog.value = true;
};

// 编辑知识点
const editKnowledgePoint = (point) => {
  currentKnowledgePoint.value = { ...point };
  knowledgePointDialog.value = true;
};

// 删除知识点
const deleteKnowledgePoint = async (id) => {
  try {
    await ElMessageBox.confirm('确认删除此知识点？', '提示', { type: 'warning' });
    await knowledgePointsStore.deleteKnowledgePoint(id);
    ElMessage.success('删除成功');
    fetchKnowledgePoints();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败');
    }
  }
};

// 处理知识点创建/编辑成功
const handleKnowledgePointSuccess = () => {
  knowledgePointDialog.value = false;
  fetchKnowledgePoints();
};

// 处理学科编辑成功
const handleSubjectSuccess = async () => {
  subjectDialog.value = false;
  await fetchSubjectDetail();
};

// 获取学科详情
const fetchSubjectDetail = async () => {
  loading.value = true;
  try {
    const data = await subjectsStore.getSubjectDetail(subjectId.value);
    subject.value = data;
  } catch (error) {
    ElMessage.error('获取学科详情失败');
  } finally {
    loading.value = false;
  }
};

// 获取知识点列表
const fetchKnowledgePoints = async () => {
  loading.value = true;
  try {
    await knowledgePointsStore.fetchKnowledgePoints(subjectId.value);
    knowledgePoints.value = knowledgePointsStore.knowledgePoints;
  } catch (error) {
    ElMessage.error('获取知识点列表失败');
  } finally {
    loading.value = false;
  }
};

// 添加路由参数变化监听，确保切换不同学科时能重新加载数据
watch(() => route.params.id, async (newId) => {
  if (newId) {
    await fetchSubjectDetail();
    await fetchKnowledgePoints();
  }
});

onMounted(async () => {
  await fetchSubjectDetail();
  await fetchKnowledgePoints();
});
</script>

<style scoped>
.subject-detail {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  display: flex;
  align-items: center;
}

.page-title h2 {
  margin: 0;
}

.subject-description {
  margin-top: 15px;
  color: #606266;
}

.content-section {
  margin-top: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h3 {
  margin: 0;
}

.ml-4 {
  margin-left: 16px;
}
</style>
