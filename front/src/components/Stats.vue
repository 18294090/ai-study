<template>
  <div class="stats-container">
    <el-card class="stat-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>文档数量</span>
        </div>
      </template>
      <div class="stat-value">{{ statsStore.stats.documents_count }}</div>
    </el-card>
    <el-card class="stat-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>问题数量</span>
        </div>
      </template>
      <div class="stat-value">{{ statsStore.stats.questions_count }}</div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted } from 'vue';
import { useStatsStore } from '@/stores/stats';

const statsStore = useStatsStore();

onMounted(() => {
  statsStore.fetchStats();
});
</script>

<style scoped>
.stats-container {
  display: flex;
  gap: 20px;
  justify-content: center;
}
.stat-card {
  flex: 1;
  max-width: 300px;
}
.stat-value {
  font-size: 2rem;
  font-weight: bold;
  text-align: center;
}
</style>
