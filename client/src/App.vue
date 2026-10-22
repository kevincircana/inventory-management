<template>
  <div class="app-shell" :class="{ collapsed: isCollapsed }">
    <div v-if="navOpen" class="sidebar-backdrop" @click="closeNav()"></div>

    <aside id="app-sidebar" class="sidebar" :class="{ open: navOpen }">
      <div class="sidebar-brand">
        <div class="logo">
          <h1>{{ t('nav.companyName') }}</h1>
          <span class="subtitle">{{ t('nav.subtitle') }}</span>
        </div>
        <button
          type="button"
          class="sidebar-toggle"
          :aria-label="t('nav.toggleSidebar')"
          :title="isCollapsed ? t('nav.expandSidebar') : t('nav.collapseSidebar')"
          aria-controls="app-sidebar"
          :aria-expanded="isCollapsed ? 'false' : 'true'"
          @click="toggleCollapsed"
        >
          <svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="2.5" y="3.5" width="15" height="13" rx="2" />
            <path d="M7.5 3.5v13" />
            <path v-if="isCollapsed" d="M11.5 8l2 2-2 2" />
            <path v-else d="M13.5 8l-2 2 2 2" />
          </svg>
        </button>
        <button type="button" class="sidebar-close" :aria-label="t('nav.closeMenu')" @click="closeNav(true)">
          <svg viewBox="0 0 20 20" width="20" height="20" fill="none" aria-hidden="true">
            <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
          </svg>
        </button>
      </div>

      <nav ref="sidebarNav" class="sidebar-nav" :aria-label="t('nav.primaryNavigation')">
        <div v-for="group in navGroups" :key="group.id" class="nav-group">
          <p class="nav-group-heading">{{ t(group.headingKey) }}</p>
          <router-link
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="nav-link"
            :class="{ active: $route.path === item.to }"
            :aria-current="$route.path === item.to ? 'page' : null"
            :aria-label="isCollapsed ? itemLabel(item) : null"
            :title="isCollapsed ? itemLabel(item) : null"
          >
            <svg class="nav-icon" viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path v-for="d in navIcons[item.to]" :key="d" :d="d" />
            </svg>
            <span class="nav-label">{{ itemLabel(item) }}</span>
          </router-link>
        </div>
      </nav>

      <div class="sidebar-footer">
        <LanguageSwitcher />
        <ProfileMenu
          @show-profile-details="showProfileDetails = true"
          @show-tasks="showTasks = true"
        />
      </div>
    </aside>

    <div class="app-main">
      <div class="mobile-bar">
        <button
          ref="menuButton"
          type="button"
          class="menu-button"
          :aria-label="t('nav.openMenu')"
          aria-controls="app-sidebar"
          :aria-expanded="navOpen ? 'true' : 'false'"
          @click="openNav"
        >
          <svg viewBox="0 0 20 20" width="20" height="20" fill="none" aria-hidden="true">
            <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
          </svg>
        </button>
        <span class="mobile-bar-title">{{ t('nav.companyName') }}</span>
      </div>

      <div v-if="showGlobalFilters" class="app-header">
        <FilterBar />
      </div>

      <main class="main-content">
        <router-view />
      </main>
    </div>

    <ProfileDetailsModal
      :is-open="showProfileDetails"
      @close="showProfileDetails = false"
    />

    <TasksModal
      :is-open="showTasks"
      :tasks="tasks"
      @close="showTasks = false"
      @add-task="addTask"
      @delete-task="deleteTask"
      @toggle-task="toggleTask"
    />
  </div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount, computed, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { api } from './api'
import { useAuth } from './composables/useAuth'
import { useI18n } from './composables/useI18n'
import FilterBar from './components/FilterBar.vue'
import ProfileMenu from './components/ProfileMenu.vue'
import ProfileDetailsModal from './components/ProfileDetailsModal.vue'
import TasksModal from './components/TasksModal.vue'
import LanguageSwitcher from './components/LanguageSwitcher.vue'

export default {
  name: 'App',
  components: {
    FilterBar,
    ProfileMenu,
    ProfileDetailsModal,
    TasksModal,
    LanguageSwitcher
  },
  setup() {
    const { currentUser } = useAuth()
    const { t } = useI18n()
    const route = useRoute()

    // Single nav definition, rendered once and shared by the desktop sidebar and the mobile drawer.
    // Labels: i18n key via `key`, or a literal string via `label`.
    const navGroups = [
      {
        id: 'operations',
        headingKey: 'nav.groupOperations',
        items: [
          { to: '/', key: 'nav.overview' },
          { to: '/inventory', key: 'nav.inventory' },
          { to: '/orders', key: 'nav.orders' },
          { to: '/audit-log', key: 'nav.auditLog' }
        ]
      },
      {
        id: 'analysis',
        headingKey: 'nav.groupAnalysis',
        items: [
          { to: '/spending', key: 'nav.finance' },
          { to: '/demand', key: 'nav.demandForecast' },
          { to: '/restocking', key: 'nav.restocking' },
          { to: '/reports', label: 'Reports' }
        ]
      }
    ]

    // Inline icon paths (20px viewBox, stroke style), keyed by route path. Rendered next to each nav label.
    const navIcons = {
      '/': ['M3 9.5L10 3l7 6.5', 'M5 8.5V16h10V8.5', 'M8.5 16v-4.5h3V16'],
      '/inventory': ['M3 6.5L10 3l7 3.5v7L10 17l-7-3.5v-7z', 'M3 6.5L10 10l7-3.5', 'M10 10v7'],
      '/orders': ['M6 3h8a1 1 0 011 1v13l-2.5-1.5L10 17l-2.5-1.5L5 17V4a1 1 0 011-1z', 'M8 7h4', 'M8 10h4'],
      '/spending': ['M3 6a1 1 0 011-1h12a1 1 0 011 1v9a1 1 0 01-1 1H4a1 1 0 01-1-1V6z', 'M3 9h14', 'M13.5 12.5h1.5'],
      '/demand': ['M3 16h14', 'M4 13l4-4 3 3 5-6', 'M12.5 6H16v3.5'],
      '/restocking': ['M4 10a6 6 0 0110.2-4.3L16 7.5', 'M16 4v3.5h-3.5', 'M16 10a6 6 0 01-10.2 4.3L4 12.5', 'M4 16v-3.5h3.5'],
      '/audit-log': ['M4 3h12v14H4V3z', 'M7 7h6', 'M7 10h6', 'M7 13h3.5'],
      '/reports': ['M5 3h7l3 3v11H5V3z', 'M12 3v3h3', 'M8 10h4', 'M8 13h4']
    }
    const itemLabel = (item) => (item.key ? t(item.key) : item.label)

    // Sidebar collapse (desktop/tablet only). A saved choice overrides the width default.
    const STORAGE_KEY = 'sidebar-collapsed'
    const readStored = () => {
      try {
        const v = window.localStorage.getItem(STORAGE_KEY)
        return v === 'true' ? true : v === 'false' ? false : null
      } catch (e) {
        return null
      }
    }
    const userCollapsed = ref(readStored())
    const wideQuery = window.matchMedia('(min-width: 1200px)')
    const isWide = ref(wideQuery.matches)
    const onWideChange = (e) => { isWide.value = e.matches }
    const isCollapsed = computed(() => (userCollapsed.value === null ? !isWide.value : userCollapsed.value))
    const toggleCollapsed = () => {
      userCollapsed.value = !isCollapsed.value
      try {
        window.localStorage.setItem(STORAGE_KEY, String(userCollapsed.value))
      } catch (e) {
        // storage unavailable: keep in-memory choice
      }
    }

    // Mobile drawer state
    const navOpen = ref(false)
    const menuButton = ref(null)
    const sidebarNav = ref(null)

    const openNav = async () => {
      navOpen.value = true
      await nextTick()
      const first = sidebarNav.value && sidebarNav.value.querySelector('a')
      if (first) first.focus()
    }
    const closeNav = (restoreFocus = false) => {
      if (!navOpen.value) return
      navOpen.value = false
      if (restoreFocus === true && menuButton.value) menuButton.value.focus()
    }
    const onKeydown = (e) => {
      if (e.key === 'Escape') closeNav(true)
    }
    const onResize = () => {
      if (window.innerWidth >= 900) closeNav()
    }

    // The audit log has its own filters and does not use the global ones, so hide the bar there.
    const showGlobalFilters = computed(() => route.path !== '/audit-log')

    watch(() => route.path, () => closeNav())
    watch(navOpen, (open) => {
      document.body.classList.toggle('nav-locked', open)
    })

    onMounted(() => {
      window.addEventListener('keydown', onKeydown)
      window.addEventListener('resize', onResize)
      wideQuery.addEventListener('change', onWideChange)
    })
    onBeforeUnmount(() => {
      wideQuery.removeEventListener('change', onWideChange)
      window.removeEventListener('keydown', onKeydown)
      window.removeEventListener('resize', onResize)
      document.body.classList.remove('nav-locked')
    })
    const showProfileDetails = ref(false)
    const showTasks = ref(false)
    const apiTasks = ref([])

    // Merge mock tasks from currentUser with API tasks
    const tasks = computed(() => {
      return [...currentUser.value.tasks, ...apiTasks.value]
    })

    const loadTasks = async () => {
      try {
        apiTasks.value = await api.getTasks()
      } catch (err) {
        console.error('Failed to load tasks:', err)
      }
    }

    const addTask = async (taskData) => {
      try {
        const newTask = await api.createTask(taskData)
        // Add new task to the beginning of the array
        apiTasks.value.unshift(newTask)
      } catch (err) {
        console.error('Failed to add task:', err)
      }
    }

    const deleteTask = async (taskId) => {
      try {
        // Check if it's a mock task (from currentUser)
        const isMockTask = currentUser.value.tasks.some(t => t.id === taskId)

        if (isMockTask) {
          // Remove from mock tasks
          const index = currentUser.value.tasks.findIndex(t => t.id === taskId)
          if (index !== -1) {
            currentUser.value.tasks.splice(index, 1)
          }
        } else {
          // Remove from API tasks
          await api.deleteTask(taskId)
          apiTasks.value = apiTasks.value.filter(t => t.id !== taskId)
        }
      } catch (err) {
        console.error('Failed to delete task:', err)
      }
    }

    const toggleTask = async (taskId) => {
      try {
        // Check if it's a mock task (from currentUser)
        const mockTask = currentUser.value.tasks.find(t => t.id === taskId)

        if (mockTask) {
          // Toggle mock task status
          mockTask.status = mockTask.status === 'pending' ? 'completed' : 'pending'
        } else {
          // Toggle API task
          const updatedTask = await api.toggleTask(taskId)
          const index = apiTasks.value.findIndex(t => t.id === taskId)
          if (index !== -1) {
            apiTasks.value[index] = updatedTask
          }
        }
      } catch (err) {
        console.error('Failed to toggle task:', err)
      }
    }

    onMounted(loadTasks)

    return {
      t,
      showGlobalFilters,
      navGroups,
      navIcons,
      itemLabel,
      isCollapsed,
      toggleCollapsed,
      navOpen,
      menuButton,
      sidebarNav,
      openNav,
      closeNav,
      showProfileDetails,
      showTasks,
      tasks,
      addTask,
      deleteTask,
      toggleTask
    }
  }
}
</script>

<style>
/* ==========================================================================
   Design tokens. Colors, spacing, radius and shadow live here only.
   ========================================================================== */
:root {
  /* Neutrals (slate) */
  --color-text: #0f172a;
  --color-text-body: #1e293b;
  --color-text-strong: #334155;
  --color-text-muted: #475569;
  --color-text-secondary: #64748b;
  --color-border: #e2e8f0;
  --color-border-strong: #cbd5e1;
  --color-border-subtle: #f1f5f9;
  --color-bg: #f8fafc;
  --color-surface: #ffffff;
  --color-hover: #f1f5f9;

  /* Accent: active nav item, primary buttons, focus ring */
  --color-accent: #2563eb;
  --color-accent-hover: #1d4ed8;
  --color-accent-soft: #eff6ff;
  --color-on-accent: #ffffff;
  --color-focus-ring: #2563eb;

  /* Status colors (status only) */
  --color-success-text: #059669;
  --color-warning-text: #ea580c;
  --color-danger-text: #dc2626;
  --color-success-bg: #d1fae5;
  --color-success-fg: #065f46;
  --color-warning-bg: #fed7aa;
  --color-warning-fg: #92400e;
  --color-danger-bg: #fecaca;
  --color-danger-fg: #991b1b;
  --color-info-bg: #dbeafe;
  --color-info-fg: #1e40af;
  --color-stable-bg: #e0e7ff;
  --color-stable-fg: #3730a3;
  --color-error-bg: #fef2f2;

  --color-backdrop: rgba(15, 23, 42, 0.45);

  /* Spacing scale (4px base) */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;

  /* Layout */
  --sidebar-width: 240px;
  --page-padding: var(--space-6);
  --page-gap: var(--space-5);
  --card-padding: var(--space-5);
  --content-max-width: 1600px;

  /* Shape and elevation */
  --radius: 8px;
  --radius-card: 10px;
  --shadow-elevated: 0 4px 12px rgba(15, 23, 42, 0.08);
}

@media (max-width: 899px) {
  :root {
    --page-padding: var(--space-4);
  }
}

/* ==========================================================================
   Base
   ========================================================================== */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  background: var(--color-bg);
  color: var(--color-text-body);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body.nav-locked {
  overflow: hidden;
}

:focus-visible {
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

/* ==========================================================================
   Shell: sidebar + main column
   ========================================================================== */
.app-shell {
  display: grid;
  grid-template-columns: var(--sidebar-width) minmax(0, 1fr);
  min-height: 100vh;
}

.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  z-index: 200;
}

.sidebar-brand {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-5) var(--space-4) var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.logo {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.logo h1 {
  font-size: 1.125rem;
  font-weight: 700;
  line-height: 1.25;
  color: var(--color-text);
  letter-spacing: -0.025em;
}

.subtitle {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
  font-weight: 400;
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4) var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.nav-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.nav-group-heading {
  padding: 0 var(--space-3);
  margin-bottom: var(--space-1);
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-secondary);
}

.nav-link {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  color: var(--color-text-secondary);
  text-decoration: none;
  font-weight: 500;
  font-size: 0.9375rem;
  border-radius: var(--radius);
  transition: background-color 0.15s ease, color 0.15s ease;
}

.nav-link:hover {
  color: var(--color-text);
  background: var(--color-hover);
}

.nav-link.active {
  color: var(--color-accent);
  background: var(--color-accent-soft);
  font-weight: 600;
}

.sidebar-footer {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border-top: 1px solid var(--color-border);
}

/* Footer utilities: full width, dropdowns open upward and stay inside the sidebar */
.sidebar .sidebar-footer .language-button,
.sidebar .sidebar-footer .profile-button {
  width: 100%;
}

.sidebar .sidebar-footer .language-label,
.sidebar .sidebar-footer .profile-name {
  flex: 1;
  min-width: 0;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar .sidebar-footer .dropdown-menu {
  top: auto;
  bottom: calc(100% + var(--space-2));
  left: 0;
  right: 0;
  min-width: 0;
  box-shadow: var(--shadow-elevated);
}

.nav-icon {
  flex-shrink: 0;
}

.nav-label {
  min-width: 0;
}

.sidebar-toggle,
.sidebar-close,
.menu-button {
  display: none;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  color: var(--color-text-strong);
  cursor: pointer;
}

.sidebar-toggle:hover,
.sidebar-close:hover,
.menu-button:hover {
  background: var(--color-hover);
}

.app-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

/* Page header row: hosts the filters, sticky at the top of the main column */
.app-header {
  position: sticky;
  top: 0;
  z-index: 90;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
  padding: var(--space-3) var(--page-padding);
}

.mobile-bar {
  display: none;
}

.sidebar-backdrop {
  display: none;
}

.main-content {
  flex: 1;
  width: 100%;
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--page-padding);
}

/* Off-canvas drawer below 900px */
@media (max-width: 899px) {
  .app-shell {
    grid-template-columns: minmax(0, 1fr);
  }

  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    height: 100%;
    width: min(var(--sidebar-width), 85vw);
    transform: translateX(-100%);
    visibility: hidden;
    transition: transform 0.2s ease, visibility 0s linear 0.2s;
    z-index: 300;
  }

  .sidebar.open {
    transform: translateX(0);
    visibility: visible;
    transition: transform 0.2s ease, visibility 0s;
    box-shadow: var(--shadow-elevated);
  }

  .sidebar-close,
  .menu-button {
    display: inline-flex;
  }

  .sidebar-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    background: var(--color-backdrop);
    z-index: 250;
  }

  .mobile-bar {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    position: sticky;
    top: 0;
    z-index: 100;
    height: 52px;
    padding: 0 var(--page-padding);
    background: var(--color-surface);
    border-bottom: 1px solid var(--color-border);
  }

  .mobile-bar-title {
    font-size: 1rem;
    font-weight: 700;
    color: var(--color-text);
    letter-spacing: -0.025em;
  }

  /* Wide tables scroll inside their card instead of widening the page */
  .card {
    min-width: 0;
    overflow-x: auto;
  }

  /* Filters take several rows on narrow screens, so they scroll with the page */
  .app-header {
    position: static;
  }
}

/* Desktop and tablet: expanded / icons-only rail */
@media (min-width: 900px) {
  .app-shell {
    transition: grid-template-columns 0.2s ease;
  }

  .app-shell.collapsed {
    --sidebar-width: 72px;
  }

  .sidebar-toggle {
    display: inline-flex;
  }

  .sidebar-nav {
    overflow-x: hidden;
  }

  .nav-link {
    overflow: hidden;
  }

  .nav-label {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .collapsed .sidebar-brand {
    justify-content: center;
    padding-left: var(--space-3);
    padding-right: var(--space-3);
  }

  .collapsed .nav-label,
  .collapsed .nav-group-heading,
  .collapsed .logo,
  .collapsed .sidebar .sidebar-footer .language-label,
  .collapsed .sidebar .sidebar-footer .profile-name {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: -1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0 0 0 0);
    clip-path: inset(50%);
    white-space: nowrap;
    border: 0;
  }

  .collapsed .sidebar-nav {
    gap: var(--space-3);
  }

  .collapsed .nav-group + .nav-group {
    border-top: 1px solid var(--color-border);
    padding-top: var(--space-3);
  }

  .collapsed .nav-link {
    justify-content: center;
    padding-left: 0;
    padding-right: 0;
  }

  /* Footer: icon-only controls. Dropdowns open upward and extend over the main column. */
  .collapsed .sidebar .sidebar-footer .language-button,
  .collapsed .sidebar .sidebar-footer .profile-button {
    justify-content: center;
    padding-left: 0;
    padding-right: 0;
  }

  .collapsed .sidebar .sidebar-footer .chevron {
    display: none;
  }

  .collapsed .sidebar .sidebar-footer .dropdown-menu {
    right: auto;
    width: max-content;
    min-width: 200px;
    max-width: min(300px, calc(100vw - 24px));
  }
}

@media (prefers-reduced-motion: reduce) {
  .app-shell,
  .sidebar,
  .sidebar.open {
    transition: none;
  }
}

/* ==========================================================================
   Page-level building blocks shared by views
   ========================================================================== */
.page-header {
  margin-bottom: var(--page-gap);
}

.page-header h2 {
  font-size: 1.875rem;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 0.375rem;
  letter-spacing: -0.025em;
}

.page-header p {
  color: var(--color-text-secondary);
  font-size: 0.938rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--page-gap);
  margin-bottom: var(--page-gap);
}

/* Cards: radius, 1px border and padding from tokens. Shadow only on hover for elevated stat cards. */
.card,
.stat-card {
  background: var(--color-surface);
  border-radius: var(--radius-card);
  border: 1px solid var(--color-border);
  padding: var(--card-padding);
}

.card {
  margin-bottom: var(--page-gap);
}

.stat-card {
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.stat-card:hover {
  border-color: var(--color-border-strong);
  box-shadow: var(--shadow-elevated);
}

.stat-label {
  color: var(--color-text-secondary);
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 0.625rem;
}

.stat-value {
  font-size: 2.25rem;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.025em;
}

.stat-card.warning .stat-value {
  color: var(--color-warning-text);
}

.stat-card.success .stat-value {
  color: var(--color-success-text);
}

.stat-card.danger .stat-value {
  color: var(--color-danger-text);
}

.stat-card.info .stat-value {
  color: var(--color-accent);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--color-border);
}

.card-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.025em;
}

/* Primary button (opt-in; scoped view buttons keep their own styles) */
.btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--color-accent);
  color: var(--color-on-accent);
  border: 1px solid var(--color-accent);
  border-radius: var(--radius);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-accent-hover);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.table-container {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

thead {
  background: var(--color-bg);
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}

th {
  text-align: left;
  padding: 0.5rem 0.75rem;
  font-weight: 600;
  color: var(--color-text-muted);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

td {
  padding: 0.5rem 0.75rem;
  border-top: 1px solid var(--color-border-subtle);
  color: var(--color-text-strong);
  font-size: 0.875rem;
}

tbody tr {
  transition: background-color 0.15s ease;
}

tbody tr:hover {
  background: var(--color-bg);
}

.badge {
  display: inline-block;
  padding: 0.313rem 0.75rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.025em;
}

.badge.success,
.badge.increasing {
  background: var(--color-success-bg);
  color: var(--color-success-fg);
}

.badge.warning,
.badge.medium {
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
}

.badge.danger,
.badge.decreasing,
.badge.high {
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
}

.badge.info,
.badge.low {
  background: var(--color-info-bg);
  color: var(--color-info-fg);
}

.badge.stable {
  background: var(--color-stable-bg);
  color: var(--color-stable-fg);
}

.loading {
  text-align: center;
  padding: 3rem;
  color: var(--color-text-secondary);
  font-size: 0.938rem;
}

.error {
  background: var(--color-error-bg);
  border: 1px solid var(--color-danger-bg);
  color: var(--color-danger-fg);
  padding: var(--space-4);
  border-radius: var(--radius);
  margin: var(--space-4) 0;
  font-size: 0.938rem;
}
</style>
