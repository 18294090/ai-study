import { createApp } from 'vue';
import { createPinia } from 'pinia';
import ElementPlus from 'element-plus';
import zhCn from 'element-plus/dist/locale/zh-cn.mjs';
import 'element-plus/dist/index.css';
import App from './App.vue';
import router from './router';
import axios from 'axios';

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(router);
app.use(ElementPlus, {
  locale: zhCn,
});

// 设置axios全局配置
app.config.globalProperties.$http = axios;
app.config.globalProperties.$baseUrl = import.meta.env.VITE_API_BASE_URL;

// 只保留一次挂载
app.mount('#app');
