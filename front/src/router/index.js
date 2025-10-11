import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

// 导入布局和视图组件
import MainLayout from '@/layouts/MainLayout.vue';
import LoginView from '@/views/LoginView.vue';
import RegisterView from '@/views/RegisterView.vue';
import DashboardView from '@/views/DashboardView.vue';
import SubjectsView from '@/views/SubjectsView.vue';
import QuestionsView from '@/views/QuestionList.vue';

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: LoginView,
  },
  {
    path: '/register',
    name: 'Register',
    component: RegisterView,
  },
  {
    path: '/',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: DashboardView,
      },
      {
        path: 'subjects',
        name: 'Subjects',
        component: SubjectsView,
      },
      {
        path: 'subjects/:id',
        name: 'SubjectDetail',
        component: () => import('@/views/SubjectDetailView.vue'),
      },
      {
        path: 'subjects/:id/knowledge-map',
        name: 'KnowledgeMap',
        component: () => import('@/views/KnowledgeMapView.vue'),
      },
      {
        path: 'questions',
        name: 'Questions',
        component: QuestionsView,
      },
      {
        path: 'mistake-book',
        name: 'MistakeBook',
        component: () => import('@/views/MistakeBookView.vue'),
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/ProfileView.vue'),
      }
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue'),
  }
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

let initialAuthCheckDone = false;

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore();

  if (!initialAuthCheckDone) {
    const token = localStorage.getItem('token');
    if (token) {
      authStore.setToken(token);
      try {
        await authStore.fetchUser();
      } catch (error) {
        authStore.logout();
      }
    }
    initialAuthCheckDone = true;
  }

  const requiresAuth = to.matched.some(record => record.meta.requiresAuth);

  if (requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'Login', query: { redirect: to.fullPath } });
  } else if ((to.name === 'Login' || to.name === 'Register') && authStore.isAuthenticated) {
    next({ name: 'Dashboard' });
  } else {
    next();
  }
});
export default router;

