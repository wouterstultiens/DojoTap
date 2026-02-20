<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import {
  clearManualToken,
  fetchAuthStatus,
  fetchBootstrap,
  loginWithCredentials,
  logoutAuth,
  setManualToken,
  submitProgress,
} from "./api";
import {
  COUNT_CAP_OPTIONS,
  DEFAULT_COUNT_CAP,
  DEFAULT_COUNT_LABEL_MODE,
  DEFAULT_TILE_SIZE_MODE,
  TIMER_OPTIONS,
  formatMinuteLabel,
} from "./constants";
import FilterBar from "./components/FilterBar.vue";
import TaskTile from "./components/TaskTile.vue";
import TilePicker from "./components/TilePicker.vue";
import type {
  AuthStatusResponse,
  BootstrapResponse,
  CountLabelMode,
  TaskItem,
  TaskUiPreferences,
  TileSizeMode,
} from "./types";

const PIN_STORAGE_KEY = "dojotap_pinned_tasks_v1";
const TAB_STORAGE_KEY = "dojotap_active_tab_v1";
const TASK_UI_PREFERENCES_STORAGE_KEY = "dojotap_task_ui_preferences_v1";
const TASK_COUNT_TEMPLATE_REGEX = /\{\{\s*count\s*\}\}/gi;

type AppTab = "pinned" | "settings";
type FlowStage = "task" | "count" | "minutes";
type ToastTone = "info" | "success" | "error";

interface LastSubmissionEntry {
  task_name: string;
  count_increment: number;
  minutes_spent: number;
  logged_at: string;
}

const bootstrapData = ref<BootstrapResponse | null>(null);
const loading = ref(false);
const fetchError = ref("");
const authRequired = ref(false);
const authBusy = ref(false);
const authError = ref("");
const authStatus = ref<AuthStatusResponse | null>(null);
const loginUsername = ref("");
const loginPassword = ref("");
const rememberRefreshToken = ref(true);
const manualTokenInput = ref("");

const activeTab = ref<AppTab>("pinned");

const cohortFilter = ref("ALL");
const categoryFilter = ref("ALL");
const searchFilter = ref("");
const pinnedOnly = ref(true);
const hideCompleted = ref(false);

const pinnedTaskIds = ref<Set<string>>(new Set());
const flowStage = ref<FlowStage>("task");
const selectedTask = ref<TaskItem | null>(null);
const selectedCount = ref<number | null>(null);
const selectedCountLabel = ref("");
const submitting = ref(false);
let toastTimer: number | null = null;

const taskUiPreferences = ref<Record<string, TaskUiPreferences>>({});

const lastSubmission = ref<LastSubmissionEntry | null>(null);

const toast = ref<{ message: string; tone: ToastTone; visible: boolean }>({
  message: "",
  tone: "info",
  visible: false,
});

function parseJson(raw: string | null): unknown {
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function sanitizeCountLabelMode(raw: unknown): CountLabelMode | null {
  if (raw === "increment" || raw === "absolute") {
    return raw;
  }
  return null;
}

function sanitizeTileSizeMode(raw: unknown): TileSizeMode | null {
  if (raw === "very-small" || raw === "small" || raw === "medium" || raw === "large") {
    return raw;
  }
  return null;
}

function sanitizeTaskUiPreferences(raw: unknown): TaskUiPreferences | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }

  const maybe = raw as Partial<TaskUiPreferences>;
  const countLabelMode = sanitizeCountLabelMode(maybe.count_label_mode);
  const tileSizeMode = sanitizeTileSizeMode(maybe.tile_size);

  if (!countLabelMode || !tileSizeMode) {
    return null;
  }

  const countCap = sanitizeCountCap(maybe.count_cap) ?? DEFAULT_COUNT_CAP;

  return {
    count_label_mode: countLabelMode,
    tile_size: tileSizeMode,
    count_cap: countCap,
  };
}

function sanitizeCountCap(raw: unknown): number | null {
  const asNumber = Number(raw);
  if (COUNT_CAP_OPTIONS.includes(asNumber)) {
    return asNumber;
  }
  return null;
}

function persistTaskUiPreferences(): void {
  localStorage.setItem(TASK_UI_PREFERENCES_STORAGE_KEY, JSON.stringify(taskUiPreferences.value));
}

function loadTaskUiPreferences(): void {
  const parsed = parseJson(localStorage.getItem(TASK_UI_PREFERENCES_STORAGE_KEY));
  if (!parsed || typeof parsed !== "object") {
    taskUiPreferences.value = {};
    return;
  }

  const next: Record<string, TaskUiPreferences> = {};
  for (const [taskId, maybePreferences] of Object.entries(parsed as Record<string, unknown>)) {
    const sanitized = sanitizeTaskUiPreferences(maybePreferences);
    if (sanitized) {
      next[taskId] = sanitized;
    }
  }

  taskUiPreferences.value = next;
  persistTaskUiPreferences();
}

function restoreTabPreference(): void {
  const cached = localStorage.getItem(TAB_STORAGE_KEY);
  if (cached === "pinned" || cached === "settings") {
    activeTab.value = cached;
  }
}

function loadPins(serverPins: string[]): void {
  const cached = localStorage.getItem(PIN_STORAGE_KEY);
  if (cached) {
    try {
      const parsed = JSON.parse(cached) as string[];
      pinnedTaskIds.value = new Set(parsed);
      return;
    } catch {
      // If cache parse fails, replace with server defaults.
    }
  }

  pinnedTaskIds.value = new Set(serverPins);
  persistPins();
}

function persistPins(): void {
  localStorage.setItem(PIN_STORAGE_KEY, JSON.stringify(Array.from(pinnedTaskIds.value)));
}

function showToast(message: string, tone: ToastTone, durationMs?: number): void {
  if (toastTimer !== null) {
    window.clearTimeout(toastTimer);
    toastTimer = null;
  }

  toast.value = { message, tone, visible: true };

  if (durationMs && durationMs > 0) {
    toastTimer = window.setTimeout(() => {
      toast.value.visible = false;
    }, durationMs);
  }
}

function dismissToast(): void {
  if (toastTimer !== null) {
    window.clearTimeout(toastTimer);
    toastTimer = null;
  }
  toast.value.visible = false;
}

async function scrollViewportToTop(): Promise<void> {
  await nextTick();
  window.scrollTo({ top: 0, left: 0, behavior: "auto" });
}

function resetFlow(): void {
  flowStage.value = "task";
  selectedTask.value = null;
  selectedCount.value = null;
  selectedCountLabel.value = "";
}

function togglePin(taskId: string): void {
  if (pinnedTaskIds.value.has(taskId)) {
    pinnedTaskIds.value.delete(taskId);
  } else {
    pinnedTaskIds.value.add(taskId);
  }
  pinnedTaskIds.value = new Set(pinnedTaskIds.value);
  persistPins();
}

function reconcileTaskUiPreferences(taskIds: string[]): void {
  const validTaskIds = new Set(taskIds);
  const next: Record<string, TaskUiPreferences> = {};
  let changed = false;

  for (const [taskId, preferences] of Object.entries(taskUiPreferences.value)) {
    if (!validTaskIds.has(taskId)) {
      changed = true;
      continue;
    }

    const sanitized = sanitizeTaskUiPreferences(preferences);
    if (!sanitized) {
      changed = true;
      continue;
    }

    next[taskId] = sanitized;
  }

  if (Object.keys(next).length !== Object.keys(taskUiPreferences.value).length) {
    changed = true;
  }

  taskUiPreferences.value = next;
  if (changed) {
    persistTaskUiPreferences();
  }
}

function resolveTaskUiPreferences(taskId: string): TaskUiPreferences {
  const explicitPreferences = taskUiPreferences.value[taskId];
  if (explicitPreferences) {
    return explicitPreferences;
  }

  return {
    count_label_mode: DEFAULT_COUNT_LABEL_MODE,
    tile_size: DEFAULT_TILE_SIZE_MODE,
    count_cap: DEFAULT_COUNT_CAP,
  };
}

function updateTaskCountLabelMode(taskId: string, mode: CountLabelMode): void {
  const normalizedMode = sanitizeCountLabelMode(mode);
  if (!normalizedMode) {
    return;
  }

  const current = resolveTaskUiPreferences(taskId);
  taskUiPreferences.value = {
    ...taskUiPreferences.value,
    [taskId]: {
      count_label_mode: normalizedMode,
      tile_size: current.tile_size,
      count_cap: current.count_cap,
    },
  };
  persistTaskUiPreferences();
}

function updateTaskTileSize(taskId: string, mode: TileSizeMode): void {
  const normalizedMode = sanitizeTileSizeMode(mode);
  if (!normalizedMode) {
    return;
  }

  const current = resolveTaskUiPreferences(taskId);
  taskUiPreferences.value = {
    ...taskUiPreferences.value,
    [taskId]: {
      count_label_mode: current.count_label_mode,
      tile_size: normalizedMode,
      count_cap: current.count_cap,
    },
  };
  persistTaskUiPreferences();
}

function updateTaskCountCap(taskId: string, raw: string): void {
  const nextCap = sanitizeCountCap(raw);
  if (!nextCap) {
    return;
  }

  const current = resolveTaskUiPreferences(taskId);
  taskUiPreferences.value = {
    ...taskUiPreferences.value,
    [taskId]: {
      count_label_mode: current.count_label_mode,
      tile_size: current.tile_size,
      count_cap: nextCap,
    },
  };
  persistTaskUiPreferences();
}

function isAuthErrorMessage(message: string): boolean {
  const normalized = message.trim().toLowerCase();
  return (
    normalized.includes("authentication required") ||
    normalized.includes("unauthorized") ||
    normalized.includes("credentials") ||
    normalized.includes("sign in")
  );
}

async function refreshAuthStatus(): Promise<void> {
  try {
    authStatus.value = await fetchAuthStatus();
    authError.value = "";
  } catch (error) {
    authError.value = error instanceof Error ? error.message : String(error);
  }
}

async function loadBootstrap(): Promise<boolean> {
  loading.value = true;
  fetchError.value = "";
  try {
    const payload = await fetchBootstrap();
    bootstrapData.value = payload;
    authRequired.value = false;
    cohortFilter.value = payload.default_filters.cohort || "ALL";
    categoryFilter.value = "ALL";
    searchFilter.value = "";
    loadPins(payload.pinned_task_ids ?? []);
    reconcileTaskUiPreferences(payload.tasks.map((task) => task.id));
    return true;
  } catch (error) {
    bootstrapData.value = null;
    fetchError.value = error instanceof Error ? error.message : String(error);
    if (isAuthErrorMessage(fetchError.value)) {
      authRequired.value = true;
      await refreshAuthStatus();
    }
    return false;
  } finally {
    loading.value = false;
  }
}

async function loginFromCredentials(): Promise<void> {
  authBusy.value = true;
  authError.value = "";
  try {
    authStatus.value = await loginWithCredentials({
      username: loginUsername.value.trim(),
      password: loginPassword.value,
      persist_refresh_token: rememberRefreshToken.value,
    });
    loginPassword.value = "";
    if (authStatus.value.authenticated) {
      await loadBootstrap();
    }
  } catch (error) {
    authError.value = error instanceof Error ? error.message : String(error);
  } finally {
    authBusy.value = false;
  }
}

async function applyManualToken(): Promise<void> {
  authBusy.value = true;
  authError.value = "";
  try {
    authStatus.value = await setManualToken({ token: manualTokenInput.value });
    manualTokenInput.value = "";
    if (authStatus.value.authenticated) {
      await loadBootstrap();
    }
  } catch (error) {
    authError.value = error instanceof Error ? error.message : String(error);
  } finally {
    authBusy.value = false;
  }
}

async function clearManualTokenOverride(): Promise<void> {
  authBusy.value = true;
  authError.value = "";
  try {
    authStatus.value = await clearManualToken();
  } catch (error) {
    authError.value = error instanceof Error ? error.message : String(error);
  } finally {
    authBusy.value = false;
  }
}

async function signOut(): Promise<void> {
  authBusy.value = true;
  authError.value = "";
  try {
    authStatus.value = await logoutAuth();
    bootstrapData.value = null;
    fetchError.value = "";
    authRequired.value = true;
    resetFlow();
  } catch (error) {
    authError.value = error instanceof Error ? error.message : String(error);
  } finally {
    authBusy.value = false;
  }
}

const cohortOptions = computed(() => bootstrapData.value?.available_cohorts ?? []);

const categoryOptions = computed(() => {
  if (!bootstrapData.value) {
    return [];
  }
  return Array.from(
    new Set(bootstrapData.value.tasks.map((task) => task.category).filter(Boolean))
  ).sort((left, right) => left.localeCompare(right));
});

const pinnedTasks = computed(() => {
  if (!bootstrapData.value) {
    return [] as TaskItem[];
  }
  return bootstrapData.value.tasks.filter((task) => pinnedTaskIds.value.has(task.id));
});

function resolveTaskTargetForCompletion(task: TaskItem): number | null {
  if (task.time_only) {
    return null;
  }

  if (typeof task.target_count === "number" && task.target_count > 0) {
    return task.target_count;
  }

  const highestKnownTarget = Math.max(...Object.values(task.counts));
  if (Number.isFinite(highestKnownTarget) && highestKnownTarget > 0) {
    return highestKnownTarget;
  }

  return null;
}

function isTaskCompleted(task: TaskItem): boolean {
  const target = resolveTaskTargetForCompletion(task);
  return target !== null && task.current_count >= target;
}

const completedPinnedCount = computed(() =>
  pinnedTasks.value.filter((task) => isTaskCompleted(task)).length
);
const authModeLabel = computed(() => {
  if (!authStatus.value) {
    return bootstrapData.value ? "Active" : "Signed out";
  }
  const mode = authStatus.value?.auth_mode ?? "none";
  if (mode === "session") {
    return "Session";
  }
  if (mode === "manual") {
    return "Manual token";
  }
  if (mode === "env") {
    return ".env token";
  }
  return "Signed out";
});
const hasManualOverride = computed(() => authStatus.value?.auth_mode === "manual");

const userDisplayName = computed(() => bootstrapData.value?.user.display_name?.trim() || "Dojo Member");
const userCohort = computed(() => bootstrapData.value?.user.dojo_cohort ?? "");
const settingsDisplayCohort = computed(() =>
  cohortFilter.value === "ALL" ? userCohort.value : cohortFilter.value
);

function resolveTaskCountForCohort(task: TaskItem, cohort: string): number | null {
  const cohortCount = task.counts[cohort];
  if (Number.isFinite(cohortCount) && cohortCount > 0) {
    return cohortCount;
  }

  const allCohortsCount = task.counts["ALL_COHORTS"];
  if (Number.isFinite(allCohortsCount) && allCohortsCount > 0) {
    return allCohortsCount;
  }

  if (typeof task.target_count === "number" && task.target_count > 0) {
    return task.target_count;
  }

  const highestKnownTarget = Math.max(...Object.values(task.counts));
  if (Number.isFinite(highestKnownTarget) && highestKnownTarget > 0) {
    return highestKnownTarget;
  }

  return null;
}

function formatTaskName(task: TaskItem, cohort: string): string {
  TASK_COUNT_TEMPLATE_REGEX.lastIndex = 0;
  if (!TASK_COUNT_TEMPLATE_REGEX.test(task.name)) {
    return task.name;
  }

  TASK_COUNT_TEMPLATE_REGEX.lastIndex = 0;
  const resolvedCount = resolveTaskCountForCohort(task, cohort);
  if (resolvedCount === null) {
    return task.name.replace(TASK_COUNT_TEMPLATE_REGEX, "?");
  }
  return task.name.replace(TASK_COUNT_TEMPLATE_REGEX, resolvedCount.toString());
}

function pinnedTaskDisplayName(task: TaskItem): string {
  return formatTaskName(task, userCohort.value);
}

function settingsTaskDisplayName(task: TaskItem): string {
  return formatTaskName(task, settingsDisplayCohort.value);
}

function formatLoggedAt(isoString: string): string {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return "just now";
  }

  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

const filteredTasks = computed(() => {
  if (!bootstrapData.value) {
    return [] as TaskItem[];
  }

  const query = searchFilter.value.trim().toLowerCase();

  return bootstrapData.value.tasks.filter((task) => {
    if (
      cohortFilter.value !== "ALL" &&
      Object.keys(task.counts).length > 0 &&
      !(cohortFilter.value in task.counts)
    ) {
      return false;
    }
    if (categoryFilter.value !== "ALL" && task.category !== categoryFilter.value) {
      return false;
    }
    if (query && !settingsTaskDisplayName(task).toLowerCase().includes(query)) {
      return false;
    }
    if (pinnedOnly.value && !pinnedTaskIds.value.has(task.id)) {
      return false;
    }
    if (hideCompleted.value && isTaskCompleted(task)) {
      return false;
    }
    return true;
  });
});

const countTileOptions = computed(() => {
  if (!selectedTask.value || selectedTask.value.time_only) {
    return [] as { value: number; label: string }[];
  }

  const preferences = resolveTaskUiPreferences(selectedTask.value.id);
  const values: { value: number; label: string }[] = [];

  for (let increment = 1; increment <= preferences.count_cap; increment += 1) {
    values.push({
      value: increment,
      label:
        preferences.count_label_mode === "absolute"
          ? (selectedTask.value.current_count + increment).toString()
          : `+${increment}`,
    });
  }

  return values;
});

const minuteTileOptions = computed(() => {
  return TIMER_OPTIONS.map((value) => ({
    value,
    label: formatMinuteLabel(value),
  }));
});

const currentTileSizeMode = computed<TileSizeMode>(() => {
  if (!selectedTask.value) {
    return DEFAULT_TILE_SIZE_MODE;
  }

  return resolveTaskUiPreferences(selectedTask.value.id).tile_size;
});

const minuteSubtitle = computed(() => {
  if (!selectedTask.value) {
    return "";
  }

  if (selectedTask.value.time_only) {
    return pinnedTaskDisplayName(selectedTask.value);
  }

  if (selectedCount.value === null) {
    return "";
  }

  return `${pinnedTaskDisplayName(selectedTask.value)} • ${
    selectedCountLabel.value || `+${selectedCount.value}`
  }`;
});

function startLogFlow(task: TaskItem): void {
  if (submitting.value) {
    return;
  }

  selectedTask.value = task;
  selectedCount.value = null;
  selectedCountLabel.value = "";
  if (task.time_only) {
    selectedCount.value = 0;
    selectedCountLabel.value = "Time only";
    flowStage.value = "minutes";
    return;
  }
  flowStage.value = "count";
}

function selectCount(value: number): void {
  if (!selectedTask.value) {
    return;
  }

  const preferences = resolveTaskUiPreferences(selectedTask.value.id);
  selectedCount.value = value;
  selectedCountLabel.value =
    preferences.count_label_mode === "absolute"
      ? `${selectedTask.value.current_count + value} (+${value})`
      : `+${value}`;

  flowStage.value = "minutes";
}

async function selectMinutes(value: number): Promise<void> {
  if (!selectedTask.value || selectedCount.value === null || submitting.value) {
    return;
  }

  const task = selectedTask.value;
  const count = selectedCount.value;

  submitting.value = true;
  showToast("Processing...", "info");

  try {
    const response = await submitProgress({
      requirement_id: task.id,
      count_increment: count,
      minutes_spent: value,
    });

    task.current_count = response.submitted_payload.newCount;
    lastSubmission.value = {
      task_name: pinnedTaskDisplayName(task),
      count_increment: count,
      minutes_spent: value,
      logged_at: new Date().toISOString(),
    };
    resetFlow();
    showToast("Done", "success", 1800);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    showToast(`Failed: ${message}. Tap a time tile to retry.`, "error", 4200);
  } finally {
    submitting.value = false;
  }
}

function pickerBack(): void {
  if (flowStage.value === "minutes") {
    if (selectedTask.value?.time_only) {
      resetFlow();
      return;
    }
    flowStage.value = "count";
    return;
  }

  resetFlow();
}

watch(activeTab, (value) => {
  localStorage.setItem(TAB_STORAGE_KEY, value);
  if (value === "settings") {
    resetFlow();
    return;
  }
  void scrollViewportToTop();
});

watch(flowStage, () => {
  void scrollViewportToTop();
});

restoreTabPreference();
loadTaskUiPreferences();
void loadBootstrap();
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand-wrap">
        <h1>DojoTap</h1>
        <p class="brand-subtitle">Tap-first progress logging for ChessDojo.</p>
      </div>

      <div class="topbar-right">
        <div v-if="bootstrapData || authStatus" class="status-strip">
          <span v-if="bootstrapData" class="status-chip chip-user">{{ userDisplayName }}</span>
          <span v-if="bootstrapData" class="status-chip chip-pinned">{{ pinnedTasks.length }} pinned</span>
          <span v-if="bootstrapData" class="status-chip chip-completed">{{ completedPinnedCount }} completed</span>
          <span class="status-chip chip-auth">Auth: {{ authModeLabel }}</span>
          <span v-if="authStatus?.has_refresh_token" class="status-chip chip-refresh">refresh saved</span>
        </div>
        <nav v-if="bootstrapData" class="tab-nav" aria-label="Primary tabs">
          <button
            type="button"
            class="tab-btn"
            :class="{ active: activeTab === 'pinned' }"
            @click="activeTab = 'pinned'"
          >
            Pinned
          </button>
          <button
            type="button"
            class="tab-btn"
            :class="{ active: activeTab === 'settings' }"
            @click="activeTab = 'settings'"
          >
            Settings
          </button>
        </nav>
        <button
          v-if="bootstrapData || authStatus?.authenticated"
          type="button"
          class="ghost-btn signout-btn"
          :disabled="authBusy"
          @click="signOut"
        >
          Sign out
        </button>
      </div>
    </header>

    <p v-if="fetchError && !authRequired" class="notice error">{{ fetchError }}</p>
    <p v-if="loading && !authRequired" class="notice">Loading tasks...</p>

    <main v-if="authRequired" class="main-view auth-view">
      <section class="auth-card">
        <h2>Sign in</h2>
        <p class="auth-copy">
          DojoTap is running in private mode. Sign in to fetch a fresh bearer token locally.
        </p>
        <p v-if="authStatus?.username" class="auth-copy">Saved account: {{ authStatus.username }}</p>
        <p v-if="authError" class="notice error">{{ authError }}</p>

        <form class="auth-form" @submit.prevent="loginFromCredentials">
          <label>
            ChessDojo email
            <input v-model.trim="loginUsername" type="email" autocomplete="username" required />
          </label>

          <label>
            Password
            <input
              v-model="loginPassword"
              type="password"
              autocomplete="current-password"
              required
            />
          </label>

          <label class="check-wrap auth-check-wrap">
            <input v-model="rememberRefreshToken" type="checkbox" />
            Save refresh token on this machine
          </label>

          <button type="submit" class="ghost-btn" :disabled="authBusy">
            {{ authBusy ? "Signing in..." : "Sign in" }}
          </button>
        </form>

        <div class="auth-divider">or</div>

        <form class="auth-form" @submit.prevent="applyManualToken">
          <label>
            Manual bearer token (fallback)
            <input
              v-model.trim="manualTokenInput"
              type="password"
              placeholder="Paste token or Bearer token"
              autocomplete="off"
              required
            />
          </label>
          <div class="auth-actions">
            <button type="submit" class="ghost-btn" :disabled="authBusy">
              {{ authBusy ? "Applying..." : "Use manual token" }}
            </button>
            <button
              v-if="hasManualOverride"
              type="button"
              class="ghost-btn"
              :disabled="authBusy"
              @click="clearManualTokenOverride"
            >
              Clear manual token
            </button>
            <button type="button" class="ghost-btn" :disabled="authBusy" @click="refreshAuthStatus">
              Refresh status
            </button>
          </div>
        </form>
      </section>
    </main>

    <main v-else-if="bootstrapData" class="main-view" :class="{ busy: submitting }">
      <section v-if="activeTab === 'pinned'" class="pane pinned-pane">
        <Transition name="stage" mode="out-in">
          <div v-if="flowStage === 'task'" key="task" class="stage-wrap task-stage">
            <p v-if="pinnedTasks.length === 0" class="empty-state">
              No pinned tasks yet. Open Settings to pin what you want here.
            </p>
            <div v-else class="pinned-grid">
              <TaskTile
                v-for="task in pinnedTasks"
                :key="task.id"
                mode="pinned"
                :task="task"
                :display-name="pinnedTaskDisplayName(task)"
                :is-pinned="true"
                :count-label-mode="resolveTaskUiPreferences(task.id).count_label_mode"
                :tile-size="resolveTaskUiPreferences(task.id).tile_size"
                :count-cap="resolveTaskUiPreferences(task.id).count_cap"
                @select="startLogFlow"
              />
            </div>

            <details v-if="pinnedTasks.length > 0 || lastSubmission" class="quick-help">
              <summary>Quick help</summary>
              <p>Tap task -> count -> time. Timer-only tasks skip the count step.</p>
              <p v-if="lastSubmission" class="last-log">
                Last: <strong>{{ lastSubmission.task_name }}</strong>
                <template v-if="lastSubmission.count_increment > 0">
                  +{{ lastSubmission.count_increment }}
                </template>
                <template v-else>time only</template>
                in {{ formatMinuteLabel(lastSubmission.minutes_spent) }}
                at {{ formatLoggedAt(lastSubmission.logged_at) }}
              </p>
            </details>
          </div>

          <div v-else-if="flowStage === 'count'" key="count" class="stage-wrap">
            <TilePicker
              title="Count"
              :subtitle="selectedTask ? pinnedTaskDisplayName(selectedTask) : ''"
              :options="countTileOptions"
              :tile-size="currentTileSizeMode"
              empty-message="No count options are configured."
              @select="selectCount"
              @back="pickerBack"
            />
          </div>

          <div v-else key="minutes" class="stage-wrap">
            <TilePicker
              title="Time"
              :subtitle="minuteSubtitle"
              :options="minuteTileOptions"
              :tile-size="currentTileSizeMode"
              empty-message="No timer options are configured."
              @select="selectMinutes"
              @back="pickerBack"
            />
          </div>
        </Transition>
      </section>

      <section v-else class="pane settings-pane">
        <div class="settings-layout">
          <aside class="settings-sidebar">
            <FilterBar
              :cohort="cohortFilter"
              :category="categoryFilter"
              :search="searchFilter"
              :pinned-only="pinnedOnly"
              :hide-completed="hideCompleted"
              :cohort-options="cohortOptions"
              :category-options="categoryOptions"
              @update-cohort="cohortFilter = $event"
              @update-category="categoryFilter = $event"
              @update-search="searchFilter = $event"
              @update-pinned-only="pinnedOnly = $event"
              @update-hide-completed="hideCompleted = $event"
              @refresh="loadBootstrap"
            />
          </aside>

          <div class="settings-list">
            <TaskTile
              v-for="task in filteredTasks"
              :key="task.id"
              mode="settings"
              :task="task"
              :display-name="settingsTaskDisplayName(task)"
              :is-pinned="pinnedTaskIds.has(task.id)"
              :count-label-mode="resolveTaskUiPreferences(task.id).count_label_mode"
              :tile-size="resolveTaskUiPreferences(task.id).tile_size"
              :count-cap="resolveTaskUiPreferences(task.id).count_cap"
              @toggle-pin="togglePin"
              @update-count-label-mode="updateTaskCountLabelMode"
              @update-tile-size="updateTaskTileSize"
              @update-count-cap="updateTaskCountCap"
            />
            <p v-if="filteredTasks.length === 0" class="empty-state">No tasks match this filter.</p>
          </div>
        </div>
      </section>
    </main>

    <Transition name="toast">
      <div v-if="toast.visible" class="toast" :class="toast.tone" role="status" @click="dismissToast">
        {{ toast.message }}
      </div>
    </Transition>
  </div>
</template>

