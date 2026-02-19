<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { fetchBootstrap, submitProgress } from "./api";
import { COUNT_OPTIONS, MINUTE_OPTIONS, formatMinuteLabel } from "./constants";
import FilterBar from "./components/FilterBar.vue";
import TaskTile from "./components/TaskTile.vue";
import TilePicker from "./components/TilePicker.vue";
import type { BootstrapResponse, TaskItem } from "./types";

const PIN_STORAGE_KEY = "dojotap_pinned_tasks_v1";
const TAB_STORAGE_KEY = "dojotap_active_tab_v1";

type AppTab = "pinned" | "settings";
type FlowStage = "task" | "count" | "minutes";
type ToastTone = "info" | "success" | "error";

const bootstrapData = ref<BootstrapResponse | null>(null);
const loading = ref(false);
const fetchError = ref("");

const activeTab = ref<AppTab>("pinned");

const cohortFilter = ref("ALL");
const categoryFilter = ref("ALL");
const searchFilter = ref("");
const pinnedOnly = ref(true);

const pinnedTaskIds = ref<Set<string>>(new Set());
const flowStage = ref<FlowStage>("task");
const selectedTask = ref<TaskItem | null>(null);
const selectedCount = ref<number | null>(null);
const submitting = ref(false);
let toastTimer: number | null = null;

const toast = ref<{ message: string; tone: ToastTone; visible: boolean }>({
  message: "",
  tone: "info",
  visible: false,
});

const countTileOptions = COUNT_OPTIONS.map((value) => ({
  value,
  label: value.toString(),
}));

const minuteTileOptions = MINUTE_OPTIONS.map((value) => ({
  value,
  label: formatMinuteLabel(value),
}));

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

function resetFlow(): void {
  flowStage.value = "task";
  selectedTask.value = null;
  selectedCount.value = null;
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

async function loadBootstrap(): Promise<void> {
  loading.value = true;
  fetchError.value = "";
  try {
    const payload = await fetchBootstrap();
    bootstrapData.value = payload;
    cohortFilter.value = payload.default_filters.cohort || "ALL";
    categoryFilter.value = "ALL";
    searchFilter.value = "";
    loadPins(payload.pinned_task_ids ?? []);
  } catch (error) {
    fetchError.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.value = false;
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

const filteredTasks = computed(() => {
  if (!bootstrapData.value) {
    return [] as TaskItem[];
  }

  const query = searchFilter.value.trim().toLowerCase();

  return bootstrapData.value.tasks.filter((task) => {
    if (cohortFilter.value !== "ALL" && !(cohortFilter.value in task.counts)) {
      return false;
    }
    if (categoryFilter.value !== "ALL" && task.category !== categoryFilter.value) {
      return false;
    }
    if (query && !task.name.toLowerCase().includes(query)) {
      return false;
    }
    if (pinnedOnly.value && !pinnedTaskIds.value.has(task.id)) {
      return false;
    }
    return true;
  });
});

function startLogFlow(task: TaskItem): void {
  if (submitting.value) {
    return;
  }

  selectedTask.value = task;
  selectedCount.value = null;
  flowStage.value = "count";
}

function selectCount(value: number): void {
  selectedCount.value = value;
  flowStage.value = "minutes";
}

async function selectMinutes(value: number): Promise<void> {
  if (!selectedTask.value || selectedCount.value === null || submitting.value) {
    return;
  }

  const task = selectedTask.value;
  const count = selectedCount.value;

  resetFlow();
  submitting.value = true;
  showToast("Processing...", "info");

  try {
    const response = await submitProgress({
      requirement_id: task.id,
      count_increment: count,
      minutes_spent: value,
    });

    task.current_count = response.submitted_payload.newCount;
    showToast("Done", "success", 1800);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    showToast(`Failed: ${message}`, "error", 3600);
  } finally {
    submitting.value = false;
  }
}

function pickerBack(): void {
  if (flowStage.value === "minutes") {
    flowStage.value = "count";
    return;
  }

  resetFlow();
}

watch(activeTab, (value) => {
  localStorage.setItem(TAB_STORAGE_KEY, value);
  if (value === "settings") {
    resetFlow();
  }
});

restoreTabPreference();
loadBootstrap();
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <h1>DojoTap</h1>
      <nav class="tab-nav" aria-label="Primary tabs">
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
    </header>

    <p v-if="fetchError" class="notice error">{{ fetchError }}</p>
    <p v-if="loading" class="notice">Loading tasks...</p>

    <main v-if="bootstrapData" class="main-view" :class="{ busy: submitting }">
      <section v-if="activeTab === 'pinned'" class="pane">
        <Transition name="stage" mode="out-in">
          <div v-if="flowStage === 'task'" key="task" class="stage-wrap">
            <p v-if="pinnedTasks.length === 0" class="empty-state">
              No pinned tasks yet. Open Settings to pin what you want here.
            </p>
            <div v-else class="pinned-grid">
              <TaskTile
                v-for="task in pinnedTasks"
                :key="task.id"
                mode="pinned"
                :task="task"
                :is-pinned="true"
                @select="startLogFlow"
              />
            </div>
          </div>

          <div v-else-if="flowStage === 'count'" key="count" class="stage-wrap">
            <TilePicker
              title="Count"
              :subtitle="selectedTask?.name || ''"
              :options="countTileOptions"
              @select="selectCount"
              @back="pickerBack"
            />
          </div>

          <div v-else key="minutes" class="stage-wrap">
            <TilePicker
              title="Time"
              :subtitle="selectedTask ? `${selectedTask.name} • +${selectedCount}` : ''"
              :options="minuteTileOptions"
              @select="selectMinutes"
              @back="pickerBack"
            />
          </div>
        </Transition>
      </section>

      <section v-else class="pane settings-pane">
        <FilterBar
          :cohort="cohortFilter"
          :category="categoryFilter"
          :search="searchFilter"
          :pinned-only="pinnedOnly"
          :cohort-options="cohortOptions"
          :category-options="categoryOptions"
          @update-cohort="cohortFilter = $event"
          @update-category="categoryFilter = $event"
          @update-search="searchFilter = $event"
          @update-pinned-only="pinnedOnly = $event"
          @refresh="loadBootstrap"
        />

        <div class="settings-list">
          <TaskTile
            v-for="task in filteredTasks"
            :key="task.id"
            mode="settings"
            :task="task"
            :is-pinned="pinnedTaskIds.has(task.id)"
            @toggle-pin="togglePin"
          />
          <p v-if="filteredTasks.length === 0" class="empty-state">No tasks match this filter.</p>
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
