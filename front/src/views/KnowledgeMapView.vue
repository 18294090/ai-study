<template>
  <div class="knowledge-map">
    <el-card>
      <template #header>
        <div class="header-content">
          <h3>知识图谱</h3>
          <el-button-group>
            <el-button size="small" @click="refreshMap">刷新</el-button>
            <el-button size="small" @click="downloadImage">导出图片</el-button>
          </el-button-group>
        </div>
      </template>
      <div ref="chartRef" class="chart-container"></div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { useRoute } from 'vue-router';
import * as echarts from 'echarts';
import { ElMessage } from 'element-plus';

const route = useRoute();
const chartRef = ref(null);
let chart = null;

const initChart = () => {
  if (chartRef.value) {
    chart = echarts.init(chartRef.value);
    const option = {
      title: {
        text: '知识点关系图'
      },
      tooltip: {},
      animationDurationUpdate: 1500,
      animationEasingUpdate: 'quinticInOut',
      series: [{
        type: 'graph',
        layout: 'force',
        symbolSize: 50,
        roam: true,
        label: {
          show: true
        },
        force: {
          repulsion: 100,
          gravity: 0.1
        },
        edgeSymbol: ['circle', 'arrow'],
        edgeSymbolSize: [4, 10],
        data: [],
        links: [],
        lineStyle: {
          opacity: 0.9,
          width: 2,
          curveness: 0
        }
      }]
    };
    chart.setOption(option);
    loadKnowledgeMapData();
  }
};

const loadKnowledgeMapData = async () => {
  try {
    const subjectId = route.params.subjectId;
    const response = await fetch(`/api/v1/analysis/analysis/knowledge-map/${subjectId}`);
    const data = await response.json();
    updateChartData(data);
  } catch (error) {
    ElMessage.error('加载知识图谱数据失败');
  }
};

const updateChartData = (data) => {
  const option = {
    series: [{
      data: data.nodes.map(node => ({
        id: node.id,
        name: node.name,
        symbolSize: 50,
        category: node.category
      })),
      links: data.links.map(link => ({
        source: link.source,
        target: link.target,
        value: link.relation
      }))
    }]
  };
  chart?.setOption(option);
};

const refreshMap = () => {
  loadKnowledgeMapData();
};

const downloadImage = () => {
  if (chart) {
    const url = chart.getDataURL();
    const link = document.createElement('a');
    link.download = '知识图谱.png';
    link.href = url;
    link.click();
  }
};

onMounted(() => {
  initChart();
  window.addEventListener('resize', () => chart?.resize());
});

onUnmounted(() => {
  chart?.dispose();
  window.removeEventListener('resize', () => chart?.resize());
});
</script>

<style scoped>
.knowledge-map {
  padding: 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-container {
  height: 600px;
  width: 100%;
}
</style>
