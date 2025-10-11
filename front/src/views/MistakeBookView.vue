<template>
  <div class="mistake-book">
    <h2>错题本</h2>
    <div class="filters">
      <el-select v-model="selectedSubject" placeholder="选择科目">
        <el-option v-for="subject in subjects" :key="subject.id" :label="subject.name" :value="subject.id" />
      </el-select>
    </div>
    <!-- 错题列表 -->
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

const selectedSubject = ref('');
const subjects = ref([]);

onMounted(async () => {
  // 获取错题本数据
});
</script>
