<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { fetchBootstrap, submitProgress } from "./api";
import {
  BUILTIN_COUNT_PROFILES,
  BUILTIN_TIMER_PROFILES,
  DEFAULT_COUNT_PROFILE_ID,
  DEFAULT_TIMER_PROFILE_ID,
  POLGAR_COUNT_PROFILE_ID,
  formatMinuteLabel,
  normalizeNumericValues,
} from "./constants";
import FilterBar from "./components/FilterBar.vue";
import TaskTile from "./components/TaskTile.vue";
import TilePicker from "./components/TilePicker.vue";
import type {
  BootstrapResponse,
  CountProfile,
  CountProfileMode,
  ProfileChoice,
  TaskItem,
  TaskProfileAssignment,
  TimerProfile,
} from "./types";

const PIN_STORAGE_KEY = "dojotap_pinned_tasks_v1";
const TAB_STORAGE_KEY = "dojotap_active_tab_v1";
const PROFILE_ASSIGNMENTS_STORAGE_KEY = "dojotap_task_profile_assignments_v1";
const CUSTOM_PROFILES_STORAGE_KEY = "dojotap_custom_profiles_v1";

const CUSTOM_COUNT_MAX = 5000;
const CUSTOM_TIMER_MAX = 720;

type AppTab = "pinned" | "settings";
type FlowStage = "task" | "count" | "minutes";
type ToastTone = "info" | "success" | "error";

type ProfileKind = "count" | "timer";

interface StoredCustomProfiles {
  count: unknown[];
  timer: unknown[];
}

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
const selectedCountLabel = ref("");
const submitting = ref(false);
let toastTimer: number | null = null;

const customCountProfiles = ref<CountProfile[]>([]);
const customTimerProfiles = ref<TimerProfile[]>([]);
const profileAssignments = ref<Record<string, TaskProfileAssignment>>({});

const newProfileKind = ref<ProfileKind>("count");
const newProfileName = ref("");
const newProfileValues = ref("");
const newCountMode = ref<CountProfileMode>("absolute");

const toast = ref<{ message: string; tone: ToastTone; visible: boolean }>({
  message: "",
  tone: "info",
  visible: false,
});

const allCountProfiles = computed(() => [...BUILTIN_COUNT_PROFILES, ...customCountProfiles.value]);
const allTimerProfiles = computed(() => [...BUILTIN_TIMER_PROFILES, ...customTimerProfiles.value]);

const countProfileById = computed(() => {
  const map = new Map<string, CountProfile>();
  for (const profile of allCountProfiles.value) {
    map.set(profile.id, profile);
  }
  return map;
});

const timerProfileById = computed(() => {
  const map = new Map<string, TimerProfile>();
  for (const profile of allTimerProfiles.value) {
    map.set(profile.id, profile);
  }
  return map;
});

const countProfileChoices = computed<ProfileChoice[]>(() =>
  allCountProfiles.value.map((profile) => ({
    id: profile.id,
    label: `${profile.name} (${profile.mode})${profile.source === "custom" ? " [custom]" : ""}`,
  }))
);

const timerProfileChoices = computed<ProfileChoice[]>(() =>
  allTimerProfiles.value.map((profile) => ({
    id: profile.id,
    label: `${profile.name}${profile.source === "custom" ? " [custom]" : ""}`,
  }))
);

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

function sanitizeValues(rawValues: unknown, maxValue: number): number[] {
  if (!Array.isArray(rawValues)) {
    return [];
  }

  const numbers = rawValues
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value) && value > 0 && value <= maxValue);

  return normalizeNumericValues(numbers);
}

function sanitizeStoredCountProfile(raw: unknown): CountProfile | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }

  const maybe = raw as Partial<CountProfile>;
  const id = typeof maybe.id === "string" ? maybe.id.trim() : "";
  const name = typeof maybe.name === "string" ? maybe.name.trim() : "";
  const mode = maybe.mode === "increment" ? "increment" : maybe.mode === "absolute" ? "absolute" : null;
  const values = sanitizeValues(maybe.values, CUSTOM_COUNT_MAX);

  if (!id || !name || mode === null || values.length === 0) {
    return null;
  }

  return {
    id,
    kind: "count",
    name,
    source: "custom",
    mode,
    values,
  };
}

function sanitizeStoredTimerProfile(raw: unknown): TimerProfile | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }

  const maybe = raw as Partial<TimerProfile>;
  const id = typeof maybe.id === "string" ? maybe.id.trim() : "";
  const name = typeof maybe.name === "string" ? maybe.name.trim() : "";
  const values = sanitizeValues(maybe.values, CUSTOM_TIMER_MAX);

  if (!id || !name || values.length === 0) {
    return null;
  }

  return {
    id,
    kind: "timer",
    name,
    source: "custom",
    values,
  };
}

function persistCustomProfiles(): void {
  const payload = {
    count: customCountProfiles.value,
    timer: customTimerProfiles.value,
  };
  localStorage.setItem(CUSTOM_PROFILES_STORAGE_KEY, JSON.stringify(payload));
}

function loadCustomProfiles(): void {
  const parsed = parseJson(localStorage.getItem(CUSTOM_PROFILES_STORAGE_KEY));
  if (!parsed || typeof parsed !== "object") {
    customCountProfiles.value = [];
    customTimerProfiles.value = [];
    return;
  }

  const source = parsed as Partial<StoredCustomProfiles>;
  const countRaw = Array.isArray(source.count) ? source.count : [];
  const timerRaw = Array.isArray(source.timer) ? source.timer : [];

  customCountProfiles.value = countRaw
    .map((entry) => sanitizeStoredCountProfile(entry))
    .filter((entry): entry is CountProfile => entry !== null);

  customTimerProfiles.value = timerRaw
    .map((entry) => sanitizeStoredTimerProfile(entry))
    .filter((entry): entry is TimerProfile => entry !== null);

  persistCustomProfiles();
}

function parseAssignment(raw: unknown): TaskProfileAssignment | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }

  const candidate = raw as Partial<TaskProfileAssignment>;
  const countProfileId =
    typeof candidate.count_profile_id === "string" ? candidate.count_profile_id.trim() : "";
  const timerProfileId =
    typeof candidate.timer_profile_id === "string" ? candidate.timer_profile_id.trim() : "";

  if (!countProfileId || !timerProfileId) {
    return null;
  }

  return {
    count_profile_id: countProfileId,
    timer_profile_id: timerProfileId,
  };
}

function loadProfileAssignments(): void {
  const parsed = parseJson(localStorage.getItem(PROFILE_ASSIGNMENTS_STORAGE_KEY));
  if (!parsed || typeof parsed !== "object") {
    profileAssignments.value = {};
    return;
  }

  const normalized: Record<string, TaskProfileAssignment> = {};
  for (const [taskId, assignment] of Object.entries(parsed as Record<string, unknown>)) {
    const parsedAssignment = parseAssignment(assignment);
    if (parsedAssignment) {
      normalized[taskId] = parsedAssignment;
    }
  }

  profileAssignments.value = normalized;
}

function persistProfileAssignments(): void {
  localStorage.setItem(PROFILE_ASSIGNMENTS_STORAGE_KEY, JSON.stringify(profileAssignments.value));
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

function resolveCountProfileId(rawId: string): string {
  if (rawId && countProfileById.value.has(rawId)) {
    return rawId;
  }
  if (countProfileById.value.has(DEFAULT_COUNT_PROFILE_ID)) {
    return DEFAULT_COUNT_PROFILE_ID;
  }
  return allCountProfiles.value[0]?.id ?? "";
}

function resolveTimerProfileId(rawId: string): string {
  if (rawId && timerProfileById.value.has(rawId)) {
    return rawId;
  }
  if (timerProfileById.value.has(DEFAULT_TIMER_PROFILE_ID)) {
    return DEFAULT_TIMER_PROFILE_ID;
  }
  return allTimerProfiles.value[0]?.id ?? "";
}

function normalizeAssignment(raw: TaskProfileAssignment | undefined): TaskProfileAssignment {
  const countProfileId = resolveCountProfileId(raw?.count_profile_id ?? "");
  const timerProfileId = resolveTimerProfileId(raw?.timer_profile_id ?? "");

  return {
    count_profile_id: countProfileId,
    timer_profile_id: timerProfileId,
  };
}

function sameAssignment(left: TaskProfileAssignment, right: TaskProfileAssignment): boolean {
  return (
    left.count_profile_id === right.count_profile_id && left.timer_profile_id === right.timer_profile_id
  );
}

function reconcileAssignments(taskIds: string[]): void {
  const next: Record<string, TaskProfileAssignment> = {};
  let changed = Object.keys(profileAssignments.value).length !== taskIds.length;

  for (const taskId of taskIds) {
    const normalized = normalizeAssignment(profileAssignments.value[taskId]);
    next[taskId] = normalized;

    const existing = profileAssignments.value[taskId];
    if (!existing || !sameAssignment(existing, normalized)) {
      changed = true;
    }
  }

  profileAssignments.value = next;
  if (changed) {
    persistProfileAssignments();
  }
}

function selectedCountProfileId(taskId: string): string {
  return normalizeAssignment(profileAssignments.value[taskId]).count_profile_id;
}

function selectedTimerProfileId(taskId: string): string {
  return normalizeAssignment(profileAssignments.value[taskId]).timer_profile_id;
}

function updateTaskCountProfile(taskId: string, profileId: string): void {
  if (!countProfileById.value.has(profileId)) {
    return;
  }

  const next = normalizeAssignment(profileAssignments.value[taskId]);
  next.count_profile_id = profileId;
  profileAssignments.value = {
    ...profileAssignments.value,
    [taskId]: next,
  };
  persistProfileAssignments();
}

function updateTaskTimerProfile(taskId: string, profileId: string): void {
  if (!timerProfileById.value.has(profileId)) {
    return;
  }

  const next = normalizeAssignment(profileAssignments.value[taskId]);
  next.timer_profile_id = profileId;
  profileAssignments.value = {
    ...profileAssignments.value,
    [taskId]: next,
  };
  persistProfileAssignments();
}

function parseManualValues(raw: string): number[] {
  return raw
    .split(/[\s,;]+/)
    .map((chunk) => Number(chunk.trim()))
    .filter((value) => Number.isFinite(value));
}

function createCustomProfile(): void {
  const name = newProfileName.value.trim();
  if (!name) {
    showToast("Give the setup a name.", "error", 2400);
    return;
  }

  const sourceValues = parseManualValues(newProfileValues.value);
  const maxValue = newProfileKind.value === "count" ? CUSTOM_COUNT_MAX : CUSTOM_TIMER_MAX;
  const values = normalizeNumericValues(sourceValues).filter((value) => value <= maxValue);

  if (values.length === 0) {
    showToast("Enter positive numbers like 1,2,3 or 60,65,70.", "error", 2800);
    return;
  }

  const id = `custom_${newProfileKind.value}_${Date.now().toString(36)}_${Math.random()
    .toString(36)
    .slice(2, 8)}`;

  if (newProfileKind.value === "count") {
    customCountProfiles.value = [
      ...customCountProfiles.value,
      {
        id,
        kind: "count",
        name,
        source: "custom",
        mode: newCountMode.value,
        values,
      },
    ];
  } else {
    customTimerProfiles.value = [
      ...customTimerProfiles.value,
      {
        id,
        kind: "timer",
        name,
        source: "custom",
        values,
      },
    ];
  }

  persistCustomProfiles();
  showToast("Setup created.", "success", 1600);
  newProfileName.value = "";
  newProfileValues.value = "";
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
    reconcileAssignments(payload.tasks.map((task) => task.id));
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

function countProfileForTask(task: TaskItem): CountProfile {
  const profileId = selectedCountProfileId(task.id);
  return (
    countProfileById.value.get(profileId) ??
    countProfileById.value.get(DEFAULT_COUNT_PROFILE_ID) ??
    allCountProfiles.value[0]
  );
}

function timerProfileForTask(task: TaskItem): TimerProfile {
  const profileId = selectedTimerProfileId(task.id);
  return (
    timerProfileById.value.get(profileId) ??
    timerProfileById.value.get(DEFAULT_TIMER_PROFILE_ID) ??
    allTimerProfiles.value[0]
  );
}

function resolveCountValues(task: TaskItem, profile: CountProfile): number[] {
  if (profile.id === POLGAR_COUNT_PROFILE_ID) {
    const values: number[] = [];
    for (let value = task.current_count + 1; value <= task.current_count + 30; value += 1) {
      values.push(value);
    }
    return values;
  }

  const values = normalizeNumericValues(profile.values);
  if (profile.mode === "absolute") {
    return values.filter((value) => value > task.current_count);
  }
  return values;
}

const countTileOptions = computed(() => {
  if (!selectedTask.value) {
    return [] as { value: number; label: string }[];
  }

  const profile = countProfileForTask(selectedTask.value);
  return resolveCountValues(selectedTask.value, profile).map((value) => ({
    value,
    label: value.toString(),
  }));
});

const minuteTileOptions = computed(() => {
  if (!selectedTask.value) {
    return [] as { value: number; label: string }[];
  }

  const profile = timerProfileForTask(selectedTask.value);
  return normalizeNumericValues(profile.values).map((value) => ({
    value,
    label: formatMinuteLabel(value),
  }));
});

const minuteSubtitle = computed(() => {
  if (!selectedTask.value || selectedCount.value === null) {
    return "";
  }
  return `${selectedTask.value.name} • ${selectedCountLabel.value || `+${selectedCount.value}`}`;
});

function startLogFlow(task: TaskItem): void {
  if (submitting.value) {
    return;
  }

  selectedTask.value = task;
  selectedCount.value = null;
  selectedCountLabel.value = "";
  flowStage.value = "count";
}

function selectCount(value: number): void {
  if (!selectedTask.value) {
    return;
  }

  const profile = countProfileForTask(selectedTask.value);
  if (profile.mode === "absolute") {
    const increment = value - selectedTask.value.current_count;
    if (increment < 1) {
      showToast("Selected count must be above current progress.", "error", 2600);
      return;
    }

    selectedCount.value = increment;
    selectedCountLabel.value = `${value} (+${increment})`;
  } else {
    selectedCount.value = value;
    selectedCountLabel.value = `+${value}`;
  }

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
loadCustomProfiles();
loadProfileAssignments();
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
                :count-profile-choices="countProfileChoices"
                :timer-profile-choices="timerProfileChoices"
                :selected-count-profile-id="selectedCountProfileId(task.id)"
                :selected-timer-profile-id="selectedTimerProfileId(task.id)"
                @select="startLogFlow"
              />
            </div>
          </div>

          <div v-else-if="flowStage === 'count'" key="count" class="stage-wrap">
            <TilePicker
              title="Count"
              :subtitle="selectedTask?.name || ''"
              :options="countTileOptions"
              empty-message="No count options are available above current progress for this setup."
              @select="selectCount"
              @back="pickerBack"
            />
          </div>

          <div v-else key="minutes" class="stage-wrap">
            <TilePicker
              title="Time"
              :subtitle="minuteSubtitle"
              :options="minuteTileOptions"
              empty-message="No timer options are available for this setup."
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

        <section class="profile-builder" data-testid="profile-builder">
          <h2>Create Tile Setup</h2>
          <div class="profile-builder-grid">
            <label>
              Setup type
              <select v-model="newProfileKind" data-testid="new-setup-kind">
                <option value="count">Count</option>
                <option value="timer">Timer</option>
              </select>
            </label>

            <label v-if="newProfileKind === 'count'">
              Count mode
              <select v-model="newCountMode" data-testid="new-count-mode">
                <option value="absolute">Absolute totals</option>
                <option value="increment">Increments</option>
              </select>
            </label>

            <label>
              Name
              <input
                v-model="newProfileName"
                type="text"
                placeholder="e.g. My Long Session"
                data-testid="new-setup-name"
              />
            </label>

            <label class="profile-values-field">
              Values
              <input
                v-model="newProfileValues"
                type="text"
                placeholder="e.g. 1,2,3,4 or 60,65,70"
                data-testid="new-setup-values"
              />
            </label>

            <button
              type="button"
              class="ghost-btn"
              data-testid="create-setup"
              @click="createCustomProfile"
            >
              Save setup
            </button>
          </div>
          <p class="profile-builder-hint">
            Reusable global setups. Values are normalized, deduplicated, and sorted.
          </p>
        </section>

        <div class="settings-list">
          <TaskTile
            v-for="task in filteredTasks"
            :key="task.id"
            mode="settings"
            :task="task"
            :is-pinned="pinnedTaskIds.has(task.id)"
            :count-profile-choices="countProfileChoices"
            :timer-profile-choices="timerProfileChoices"
            :selected-count-profile-id="selectedCountProfileId(task.id)"
            :selected-timer-profile-id="selectedTimerProfileId(task.id)"
            @toggle-pin="togglePin"
            @update-count-profile="updateTaskCountProfile"
            @update-timer-profile="updateTaskTimerProfile"
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
