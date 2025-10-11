<template>
  <div class="dashboard-container">
    <el-row :gutter="20">
      <el-col :span="24">
        <h2>仪表盘</h2>
      </el-col>
    </el-row>
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card>
          <template #header>科目统计</template>
          <div>总科目数：{{ subjectsCount }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>题目统计</template>
          <div>总题目数：{{ questionsCount }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>错题统计</template>
          <div>错题数：{{ mistakesCount }}</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { useSubjectsStore } from '@/stores/subjects';
import { useQuestionsStore } from '@/stores/questions';
import http from '../utils/http'; // 假设有http工具用于API调用

// 从stores获取数据
const subjectsStore = useSubjectsStore();
const questionsStore = useQuestionsStore();

// 使用computed确保响应式更新
const subjectsCount = computed(() => subjectsStore.subjects.length);
const questionsCount = computed(() => questionsStore.questions.length);
const mistakesCount = ref(0);


</script>
