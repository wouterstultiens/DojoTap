<script setup lang="ts">
import type { ProfileChoice, TaskItem } from "../types";

defineProps<{
  task: TaskItem;
  isPinned: boolean;
  mode: "pinned" | "settings";
  countProfileChoices: ProfileChoice[];
  timerProfileChoices: ProfileChoice[];
  selectedCountProfileId: string;
  selectedTimerProfileId: string;
}>();

const emit = defineEmits<{
  select: [task: TaskItem];
  togglePin: [taskId: string];
  updateCountProfile: [taskId: string, profileId: string];
  updateTimerProfile: [taskId: string, profileId: string];
}>();
</script>

<template>
  <article v-if="mode === 'settings'" class="settings-task-row">
    <div class="settings-header-row">
      <div class="settings-meta">
        <p class="task-row-category">{{ task.category }}</p>
        <h3 class="task-row-name">{{ task.name }}</h3>
      </div>
      <button class="pin-toggle" @click="emit('togglePin', task.id)" type="button">
        {{ isPinned ? "Unpin" : "Pin" }}
      </button>
    </div>

    <div class="setup-controls">
      <label class="setup-field">
        Count setup
        <select
          :value="selectedCountProfileId"
          :data-testid="`count-profile-${task.id}`"
          @change="
            emit(
              'updateCountProfile',
              task.id,
              ($event.target as HTMLSelectElement).value
            )
          "
        >
          <option v-for="choice in countProfileChoices" :key="choice.id" :value="choice.id">
            {{ choice.label }}
          </option>
        </select>
      </label>

      <label class="setup-field">
        Timer setup
        <select
          :value="selectedTimerProfileId"
          :data-testid="`timer-profile-${task.id}`"
          @change="
            emit(
              'updateTimerProfile',
              task.id,
              ($event.target as HTMLSelectElement).value
            )
          "
        >
          <option v-for="choice in timerProfileChoices" :key="choice.id" :value="choice.id">
            {{ choice.label }}
          </option>
        </select>
      </label>
    </div>
  </article>

  <button
    v-else
    class="pinned-title-tile"
    :data-testid="`pinned-task-${task.id}`"
    type="button"
    @click="emit('select', task)"
  >
    <span>{{ task.name }}</span>
  </button>
</template>
