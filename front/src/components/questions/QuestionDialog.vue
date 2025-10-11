<template>
  <el-dialog
    v-model="visible"
    :title="isEditComputed ? '编辑题目' : '新建题目'"
    width="60%"
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="100px"
    >
      <!-- 新增：标题 -->
      <el-form-item label="标题" prop="title">
        <el-input v-model="form.title" placeholder="请输入题目标题（最多255字符）" />
      </el-form-item>

      <el-form-item label="科目" prop="subject">
        <el-select
          v-model="form.subject"
          value-key="id"
          placeholder="选择科目"
        >
          <el-option
            v-for="subject in subjectsOptions"
            :key="`subject-${subject.id}`"
            :label="subject.name"
            :value="subject"
          />
        </el-select>
      </el-form-item>

      <!-- 修改：题型 v-model 改为 form.type -->
      <el-form-item label="题型" prop="type">
        <el-select v-model="form.type" placeholder="选择题型">
          <!-- 改为后端需要的小写枚举值 -->
          <el-option label="单选题" value="single_choice" />
          <el-option label="多选题" value="multiple_choice" />
          <el-option label="填空题" value="fill_in_blank" />
          <el-option label="简答题" value="short_answer" />
        </el-select>
      </el-form-item>

      <el-form-item label="题目内容" prop="content" >
        <div class="editor-container">
          <quill-editor
            v-if="editorReady"
            ref="quillRef"
            v-model="form.content"
            :options="editorOptions"
            @blur="onEditorBlur($event)"
            class="editor"
          />
        </div>
      </el-form-item>

      <el-form-item label="答案" prop="answer">
        <el-input
          v-model="form.answer"
          type="textarea"
          :rows="2"
          placeholder="请输入答案（根据题型填写：单选A，多选AC；填空按行分隔；简答直接输入）"
        />
      </el-form-item>

      <el-form-item label="解析" prop="explanation">
        <el-input
          v-model="form.explanation"
          type="textarea"
          :rows="3"
          placeholder="请输入题目解析"
        />
      </el-form-item>

      <el-form-item label="难度" prop="difficulty">
        <el-rate v-model="form.difficulty" :max="5" />
      </el-form-item>

      <!-- 修改：prop 与 v-model 改为 knowledge_point_ids -->
      <el-form-item label="知识点" prop="knowledge_point_ids">
        <el-select
          v-model="form.knowledge_point_ids"
          multiple
          filterable
          remote
          placeholder="请选择知识点"
          :remote-method="searchKnowledgePoints"
          :loading="loading"
        >
          <el-option
            v-for="point in knowledgePoints"
            :key="`point-${point.id}`"
            :label="point.name"
            :value="point.id"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, defineEmits, watch, onMounted, computed, nextTick } from 'vue';
import { ElMessage } from 'element-plus';
import { QuillEditor, Quill } from '@vueup/vue-quill'; // 新增：从 @vueup/vue-quill 获取 Quill 实例
import '@vueup/vue-quill/dist/vue-quill.snow.css'; // 修正样式路径
import api from '@/services/api';
import { knowledgePointsApi } from '@/services/knowledgePoints';
import { useSubjectsStore } from '@/stores/subjects';
const store = useSubjectsStore();
import { questionsApi } from '../../services/questions';
import { subjectsApi } from '@/services/subjects';
// 解析后端返回的URL（兼容多种返回结构）
const extractUploadUrl = (res) => {
  const d = res?.data ?? res;
  return d?.url
    || d?.data?.url
    || d?.files?.[0]?.url
    || (Array.isArray(d) && d[0]?.url)
    || '';
};

// 封装一次上传尝试（可切换字段名与路径）
const tryUpload = async (path, fieldName, blob, filename) => {
  const fd = new FormData();
  fd.append(fieldName, blob, filename);
  const res = await api.post(path, fd); // 让浏览器自动设置 boundary
  const url = extractUploadUrl(res);
  if (!url) throw new Error('未从上传响应中解析到URL');
  return url;
};

// 统一上传图片（base64 -> url）：根据mime决定文件后缀，带重试（优先 files）
const uploadImage = async (dataUrl) => {
  const blob = dataURLToBlob(dataUrl);
  const mimeMatch = dataUrl.match(/^data:([\w/+.-]+);base64,/);
  const mime = mimeMatch?.[1] || 'image/png';
  const ext = mime.split('/')[1] || 'png';
  const filename = `image.${ext}`;

  const candidates = [
    { path: '/api/v1/upload', field: 'files' },
    { path: '/api/v1/upload', field: 'file' },
    { path: '/upload', field: 'files' },
    { path: '/upload', field: 'file' }
  ];

  let lastErr;
  for (const c of candidates) {
    try {
      return await tryUpload(c.path, c.field, blob, filename);
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr || new Error('图片上传失败');
};

// 将 base64 转 Blob
const dataURLToBlob = (dataURL) => {
  const arr = dataURL.split(',');
  const mime = arr[0].match(/:(.*?);/)[1];
  const bstr = atob(arr[1]);
  let n = bstr.length;
  const u8arr = new Uint8Array(n);
  while (n--) u8arr[n] = bstr.charCodeAt(n);
  return new Blob([u8arr], { type: mime });
};

// 处理富文本中的图片：替换为 URL，并清理非法属性名
const processImagesInContent = async (content) => {
  const div = document.createElement('div');
  div.innerHTML = content || '';
  const imgElements = div.querySelectorAll('img');
  const tasks = [];
  imgElements.forEach((img) => {
    const src = img.getAttribute('src') || '';
    if (src.startsWith('data:')) {
      tasks.push(
        uploadImage(src).then((url) => img.setAttribute('src', url))
      );
    }
  });
  await Promise.all(tasks);
  // 清理纯数字属性名，避免 setAttribute 报错
  div.querySelectorAll('*').forEach((el) => {
    const attrs = Array.from(el.attributes).map(a => a.name);
    attrs.forEach((name) => { if (/^\d+$/.test(name)) el.removeAttribute(name); });
  });
  return div.innerHTML;
};

const imageHandler = function() {
  const input = document.createElement('input');
  input.setAttribute('type', 'file');
  input.setAttribute('accept', 'image/*');
  input.click();
  input.onchange = () => {
    const file = input.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = reader.result;
        const quill = this.quill;
        const range = quill.getSelection(true);
        quill.insertEmbed(range.index, 'image', base64);
      };
      reader.readAsDataURL(file);
    }
  };
};

// 控制编辑器挂载时机
const editorReady = ref(false);
const editorOptions = ref({
  theme: 'snow',
  placeholder: '请输入内容...',
  modules: {
    toolbar: {
      container: [
        ['bold', 'italic', 'underline'],
        [{ list: 'ordered' }, { list: 'bullet' }],
        [{ align: [] }],
        ['image'],
        ['link'],
        ['clean']
      ],
      handlers: { image: imageHandler }
    }
    // 初始不配置 imageResize，待检测后按需注入
  }
});

// 动态按需注册图片缩放模块（仅在 Quill v2 兼容时注册，使用 blotFormatter 支持缩放）
onMounted(async () => {
  try {
    const BlotFormatter = await import('quill-blot-formatter').catch(() => null);
    if (BlotFormatter?.default) {
      Quill.register('modules/blotFormatter', BlotFormatter.default);
      editorOptions.value = {
        ...editorOptions.value,
        modules: {
          ...editorOptions.value.modules,
          blotFormatter: {}
        }
      };
    }
  } finally {
    editorReady.value = true;
  }
});

const onEditorBlur = (quill) => {
  // 可选：处理编辑器失去焦点事件
};
const props = defineProps({
  modelValue: Boolean,
  question: {
    type: Object,
    default: () => ({})
  },
  isEdit: {  // 添加isEdit prop
    type: Boolean,
    default: false
  }
});
const emit = defineEmits(['update:modelValue', 'submit']);
const visible = ref(false);
const loading = ref(false);
const subjects = computed(() => store.subjects);
const subjectsOptions = ref([]); // 用于下拉显示的科目列表
const knowledgePoints = ref([]);  // 修改为ref
const formRef = ref(null);
const quillRef = ref(null);
// 修改：表单字段对齐后端
const form = ref({
  id: undefined,
  title: '',
  content: '',
  answer: '',
  type: '',
  difficulty: 3,
  subject: null,
  subject_id: '',
  explanation: '',
  knowledge_point_ids: []
});
// 新增：统一判断编辑态
const isEditComputed = computed(() => Boolean(form.value?.id || props.question?.id || props.isEdit));
function preloadSubjects() {
  if (Array.isArray(subjects.value) && subjects.value.length > 0) {
    subjectsOptions.value = subjects.value;
    return;
  }
  // 否则调用后端
  subjectsApi.getSubjects('/api/v1/subjects').then(res => {
    const list = Array.isArray(res.data?.items) ? res.data.items : (Array.isArray(res.data) ? res.data : []);
    subjectsOptions.value = list;
  }).catch(() => {
    subjectsOptions.value = [];
    ElMessage.error('获取科目失败');
  });
}

// 校验规则更新：新增 title；question_type 改为 type；answer 读取 form.type
const rules = {
  title: [
    { required: true, message: '请输入标题', trigger: 'blur' },
    { min: 1, max: 255, message: '标题长度不超过255字符', trigger: 'blur' }
  ],
  subject: [{ required: true, message: '请选择科目', trigger: 'change' }],
  type: [{ required: true, message: '请选择题型', trigger: 'change' }],
  content: [
    {
      required: true,
      validator: (rule, value, callback) => {
        if (!hasMeaningfulContent(value)) {
          callback(new Error('请输入题目内容或插入图片'));
        } else {
          callback();
        }
      },
      trigger: 'blur'
    }
  ],
  answer: [
    { required: true, message: '请输入答案', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        const type = form.value.type;
        if (type === 'single_choice') {
          if (!/^[A-Z]$/.test(value)) return callback(new Error('单选题答案只能是单个A-Z字母'));
        } else if (type === 'multiple_choice') {
          if (!/^[A-Z]+$/.test(value)) return callback(new Error('多选题答案只能是A-Z字母'));
        }
        callback();
      },
      trigger: 'blur'
    }
  ],
  knowledge_point_ids: [{ type: 'array', required: false, trigger: 'change' }]
};

// 仅在选择题时将答案转为大写
watch(() => form.value.answer, (newVal) => {
  if (['single_choice', 'multiple_choice'].includes(form.value.type)) {
    if (newVal && newVal !== newVal.toUpperCase()) {
      form.value.answer = newVal.toUpperCase();
    }
  }
});

// 打开对话框时（新建）预加载科目，并默认选第一个触发知识点加载
watch(() => visible.value, async (val) => {
  if (val) {
    await preloadSubjects();
    if (!isEditComputed.value && !form.value.subject && subjectsOptions.value.length > 0) {
      form.value.subject = subjectsOptions.value[0];
    }
  }
  emit('update:modelValue', val);
});


// 根据subject对象同步subject_id，并联动加载知识点
watch(() => form.value.subject, (sub) => {
  form.value.subject_id = sub?.id ?? '';
  if (sub?.id) {
    fetchKnowledgePoints(sub.id);
  } else {
    knowledgePoints.value = [];
  }
});
// 初始化与科目列表变化时，同步一次subject对象（用于编辑态）
function syncSubjectObject() {
  if (!form.value.subject && form.value.subject_id && Array.isArray(subjectsOptions.value)) {
    const matched =
      subjectsOptions.value.find(s => s.id === form.value.subject_id) ||
      subjectsOptions.value.find(s => Number(s.id) === Number(form.value.subject_id)) ||
      null;
    form.value.subject = matched;
    if (matched?.id) fetchKnowledgePoints(matched.id);
  }
}

// 将后端返回的HTML规范化：补全相对URL为绝对地址，移除非法属性
const normalizeServerContent = (html) => {
  const base = (api?.defaults?.baseURL || window.location.origin || '').replace(/\/+$/, '') + '/';
  const safe = typeof html === 'string' ? html : '';
  const doc = new DOMParser().parseFromString(safe, 'text/html');

  // 1) 补全常见资源的相对URL
  const withUrlAttr = ['img[src]', 'a[href]', 'video[src]', 'source[src]'];
  doc.querySelectorAll(withUrlAttr.join(',')).forEach((el) => {
    ['src', 'href'].forEach((attr) => {
      const val = el.getAttribute(attr);
      if (!val) return;
      // 跳过 data: 与绝对 http(s)
      if (/^(data:|https?:\/\/)/i.test(val)) return;
      try {
        const abs = new URL(val, base).toString();
        el.setAttribute(attr, abs);
      } catch {
        /* 忽略URL解析异常 */
      }
    });
  });

  // 2) 清理纯数字属性名，避免patchAttr报错
  doc.querySelectorAll('*').forEach((el) => {
    const attrs = Array.from(el.attributes).map(a => a.name);
    attrs.forEach((name) => { if (/^\d+$/.test(name)) el.removeAttribute(name); });
  });

  return doc.body.innerHTML;
};

// 将内容写入Quill（若未挂载则回退到v-model）
const setEditorHTML = async (html) => {
  await nextTick();
  const quill = quillRef.value?.getQuill?.() || quillRef.value?.getEditor?.();
  if (quill?.clipboard?.dangerouslyPasteHTML) {
    quill.clipboard.dangerouslyPasteHTML(html || '');
  } else {
    form.value.content = html || '';
  }
};

// 监听 props.question 初始化表单并规范化content后写入编辑器
watch(() => props.question, async (val) => {
  if (val) {
    const normalized = normalizeServerContent(val.content || '');
    form.value = {
      id: val.id,
      title: val.title || '',
      content: normalized,
      answer: typeof val.answerRaw === 'string' ? val.answerRaw : answerObjToRaw(val.type, val.answer),
      type: val.type || '',
      difficulty: val.difficulty ?? 3,
      subject: typeof val.subject === 'object' && val.subject ? val.subject : null,
      subject_id: (val.subject && val.subject.id) ?? val.subject_id ?? '',
      explanation: val.explanation || '',
      knowledge_point_ids: Array.isArray(val.knowledge_point_ids)
        ? val.knowledge_point_ids
        : (Array.isArray(val.knowledge_points) ? val.knowledge_points.map(k => k.id) : [])
    };
    syncSubjectObject();
    await setEditorHTML(normalized);
  }
}, { immediate: true });

// 新建打开时，确保编辑器清空后可正常显示
watch(() => visible.value, async (val) => {
  if (val) {
    await preloadSubjects();
    if (!isEditComputed.value && !form.value.subject && subjectsOptions.value.length > 0) {
      form.value.subject = subjectsOptions.value[0];
    }
    // 确保编辑器显示的是表单里的最新内容
    await setEditorHTML(form.value.content || '');
  }
  emit('update:modelValue', val);
});

// 根据subject对象同步subject_id，并联动加载知识点
watch(() => form.value.subject, (sub) => {
  form.value.subject_id = sub?.id ?? '';
  if (sub?.id) {
    fetchKnowledgePoints(sub.id);
  } else {
    knowledgePoints.value = [];
  }
});

// 将后端结构化答案转换为可编辑字符串
function answerObjToRaw(type, answer) {
  if (!answer) return '';
  const a = typeof answer === 'string' ? (() => { try { return JSON.parse(answer); } catch { return null; } })() : answer;
  if (!a || typeof a !== 'object') return '';
  switch (type) {
    case 'single_choice': return a.choice ?? '';
    case 'multiple_choice': return Array.isArray(a.choices) ? a.choices.join('') : '';
    case 'fill_in_blank': return Array.isArray(a.blanks) ? a.blanks.join('\n') : '';
    case 'short_answer': return a.text ?? a.value ?? '';
    default: return a.value ?? '';
  }
}

// 监听modelValue变化
watch(() => props.modelValue, (val) => {
  visible.value = val;
});
// 监听visible变化
watch(() => visible.value, (val) => {
  emit('update:modelValue', val);
});

// 获取指定学科的所有知识点
const fetchKnowledgePoints = async (subjectId) => {
  if (subjectId) {
    loading.value = true;
    try {
      const res = await knowledgePointsApi.getKnowledgePoints(subjectId);  // 直接调用
      knowledgePoints.value = res.data;
    } catch (error) {
      knowledgePoints.value = [];
      ElMessage.error('获取知识点失败');
    } finally {
      loading.value = false;
    }
  } else {
    knowledgePoints.value = [];
  }
};
// 补全：远程搜索知识点（按学科与关键词过滤）
const searchKnowledgePoints = async (query) => {
  if (!form.value.subject_id) {
    knowledgePoints.value = [];
    return;
  }
  loading.value = true;
  try {
    const res = await knowledgePointsApi.getKnowledgePoints(form.value.subject_id, query || '');
    knowledgePoints.value = res.data;
  } catch (e) {
    ElMessage.error('搜索知识点失败');
  } finally {
    loading.value = false;
  }
};

const handleClose = () => {
  visible.value = false;
  form.value = {
    id: undefined,
    title: '',
    content: '',
    answer: '',
    type: '',
    difficulty: 3,
    subject: null,
    subject_id: '',
    explanation: '',
    knowledge_point_ids: []
  };
  // 重置编辑器内容，确保清空
  nextTick(() => {
    const quill = quillRef.value?.getQuill?.() || quillRef.value?.getEditor?.();
    if (quill) {
      quill.setContents([]);
    }
  });
};

const handleSubmit = async () => {
  try {
    await formRef.value.validate();
    // 从 Quill 实例读取当前最新 HTML，避免v-model滞后
    const quill = quillRef.value?.getQuill?.() || quillRef.value?.getEditor?.();
    const currentHtml = quill?.root?.innerHTML ?? form.value.content;

    // 处理富文本中的图片并替换为URL
    const processedContent = await processImagesInContent(currentHtml);
    // 回填到表单，保持编辑器与提交一致
    form.value.content = processedContent;

    const structuredAnswer = buildAnswer(form.value.type, form.value.answer);

    const payload = {
      title: form.value.title.trim(),
      content: processedContent,
      content_format: 'html',
      type: form.value.type,
      difficulty: Number(form.value.difficulty),
      subject_id: form.value.subject?.id ? Number(form.value.subject.id) : null, // 修复：使用null，而非None
      // QuestionCreate/Update 公共字段
      options: null,
      options_format: 'html',
      explanation: form.value.explanation || null,
      explanation_format: 'html',
      tags: [],
      source: null,
      status: 'draft',
      answer: structuredAnswer,
      knowledge_point_ids: (form.value.knowledge_point_ids || []).map(Number)
    };

    const isEditMode = isEditComputed.value;
    if (isEditMode) {
      await questionsApi.updateQuestion(form.value.id, payload);
    } else {
      const res = await questionsApi.createQuestion(payload);
      form.value.id = res?.data?.id;
    }
    ElMessage.success('保存成功');
    emit('submit', payload);
    handleClose();
  } catch (error) {
    console.error('保存失败', error);
    ElMessage.error('保存失败');
  }
};

// 将字符串答案转换为结构化答案（保持不变，入参 type 已是小写）
function buildAnswer(type, raw) {
  const v = (raw || '').toString().toUpperCase().trim();
  if (type === 'single_choice') {
    return { choice: v.charAt(0) || '' };
  }
  if (type === 'multiple_choice') {
    const arr = Array.from(new Set(v.split('').filter(c => /[A-Z]/.test(c))));
    return { choices: arr };
  }
  if (type === 'fill_in_blank') {
    const blanks = v.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
    return { blanks };
  }
  if (type === 'short_answer') {
    return { text: raw || '' };
  }
  return { value: raw || '' };
}

// 判定富文本是否有“有效内容”（文本或图片）
const hasMeaningfulContent = (html) => {
  // 1) 尝试使用 Quill Delta 检测
  try {
    const quill =
      quillRef.value?.getQuill?.() ||
      quillRef.value?.getEditor?.(); // 兼容不同版本API
    const ops = quill?.getContents?.()?.ops || [];
    if (ops.length) {
      const hasDeltaContent = ops.some(op => {
        if (typeof op.insert === 'object' && op.insert?.image) return true;
        if (typeof op.insert === 'string') {
          // 去除换行/空格/nbsp/零宽空格后判断
          const text = op.insert
            .replace(/\u00A0/g, ' ')
            .replace(/\u200B/g, '')
            .replace(/\s+/g, '')
            .trim();
          return text.length > 0;
        }
        return false;
      });
      if (hasDeltaContent) return true;
    }
  } catch (e) {
    // 忽略Delta检测异常，回退到HTML解析
  }

  // 2) 回退到 HTML 解析
  const safeHtml = typeof html === 'string' ? html : '';
  const doc = new DOMParser().parseFromString(safeHtml, 'text/html');
  const hasImg = !!doc.querySelector('img');
  const text = (doc.body.textContent || '')
    .replace(/\u00A0/g, ' ')  // nbsp
    .replace(/\u200B/g, '')   // 零宽空格
    .trim();
  const hasText = text.length > 0;
  return hasImg || hasText;
};
</script>

<style scoped>
  .dialog-footer {
    text-align: right;
  }
  .editor-container {
    width: 100%;
    
    margin: 0 auto;
  }
  .editor {
    height: 500px;
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  }
  .editor :deep(.ql-toolbar) {
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    border-bottom: 1px solid #dcdfe6;
    background-color: #f5f7fa;
    padding: 8px;
    order: -1;
  }
  .editor :deep(.ql-container) {
    border-bottom-left-radius: 4px;
    border-bottom-right-radius: 4px;
    flex: 1;
    font-size: 16px;
    order: 1;
  }
  .editor :deep(.ql-editor) {
    min-height: 300px;
    padding: 15px;
    line-height: 1.6;
  }
  /* 新增：图片在容器内自适应，避免溢出 */
  .editor :deep(.ql-editor) img {
    max-width: 100%;
    height: auto;
  }
</style>