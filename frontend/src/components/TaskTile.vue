<script setup lang="ts">
import type { CountLabelMode, TaskItem, TileSizeMode } from "../types";

defineProps<{
  task: TaskItem;
  displayName: string;
  isPinned: boolean;
  mode: "pinned" | "settings";
  countLabelMode: CountLabelMode;
  tileSize: TileSizeMode;
  countCap: number;
}>();

const emit = defineEmits<{
  select: [task: TaskItem];
  togglePin: [taskId: string];
  updateCountLabelMode: [taskId: string, mode: CountLabelMode];
  updateTileSize: [taskId: string, mode: TileSizeMode];
  updateCountCap: [taskId: string, cap: string];
}>();

function resolveTarget(task: TaskItem): number {
  if (typeof task.target_count === "number" && task.target_count > 0) {
    return task.target_count;
  }

  const highestCohortTarget = Math.max(...Object.values(task.counts));
  if (Number.isFinite(highestCohortTarget) && highestCohortTarget > 0) {
    return highestCohortTarget;
  }

  return Math.max(task.current_count, 1);
}

function progressPercent(task: TaskItem): number {
  const target = resolveTarget(task);
  const raw = (task.current_count / target) * 100;
  return Math.min(100, Math.max(2, raw));
}

function progressLabel(task: TaskItem): string {
  if (task.time_only) {
    return "Time only";
  }

  const target = resolveTarget(task);
  if (target <= 0) {
    return `${task.current_count}`;
  }

  return `${task.current_count} / ${target}`;
}
</script>

<template>
  <article v-if="mode === 'settings'" class="settings-task-row">
    <div class="settings-header-row">
      <div class="settings-meta">
        <p class="task-row-category">{{ task.category }}</p>
        <h3 class="task-row-name">{{ displayName }}</h3>
      </div>
      <button class="pin-toggle" @click="emit('togglePin', task.id)" type="button">
        {{ isPinned ? "Unpin" : "Pin" }}
      </button>
    </div>
    <div class="settings-controls">
      <template v-if="!task.time_only">
        <label class="settings-field">
          Label
          <select
            :value="countLabelMode"
            :data-testid="`count-label-mode-${task.id}`"
            @change="
              emit(
                'updateCountLabelMode',
                task.id,
                ($event.target as HTMLSelectElement).value as CountLabelMode
              )
            "
          >
            <option value="increment">+N</option>
            <option value="absolute">Absolute</option>
          </select>
        </label>
      </template>

      <label class="settings-field">
        Tiles
        <select
          :value="tileSize"
          :data-testid="`tile-size-${task.id}`"
          @change="
            emit(
              'updateTileSize',
              task.id,
              ($event.target as HTMLSelectElement).value as TileSizeMode
            )
          "
        >
          <option value="large">Large</option>
          <option value="medium">Medium</option>
          <option value="small">Small</option>
          <option value="very-small">Very small</option>
        </select>
      </label>

      <template v-if="!task.time_only">
        <label class="settings-field">
          Count cap
          <select
            :value="countCap"
            :data-testid="`count-cap-${task.id}`"
            @change="emit('updateCountCap', task.id, ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="cap in 200" :key="cap" :value="cap">
              {{ cap }}
            </option>
          </select>
        </label>
      </template>
    </div>
    <p class="task-row-progress">{{ progressLabel(task) }}</p>
  </article>

  <article v-else class="pinned-title-tile">
    <button
      class="pinned-select-btn"
      :data-testid="`pinned-task-${task.id}`"
      type="button"
      @click="emit('select', task)"
    >
      <div class="pinned-task-head">
        <p class="pinned-task-category">{{ task.category }}</p>
        <p class="pinned-task-progress">{{ progressLabel(task) }}</p>
      </div>
      <h3 class="pinned-task-name">{{ displayName }}</h3>
      <div v-if="!task.time_only" class="pinned-task-track" aria-hidden="true">
        <span class="pinned-task-track-fill" :style="{ width: `${progressPercent(task)}%` }"></span>
      </div>
    </button>
  </article>
</template>
