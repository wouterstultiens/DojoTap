<script setup lang="ts">
import type { TaskItem } from "../types";

defineProps<{
  task: TaskItem;
  isPinned: boolean;
  mode: "pinned" | "settings";
}>();

const emit = defineEmits<{
  select: [task: TaskItem];
  togglePin: [taskId: string];
}>();
</script>

<template>
  <article v-if="mode === 'settings'" class="settings-task-row">
    <div class="settings-meta">
      <p class="task-row-category">{{ task.category }}</p>
      <h3 class="task-row-name">{{ task.name }}</h3>
    </div>
    <button class="pin-toggle" @click="emit('togglePin', task.id)" type="button">
      {{ isPinned ? "Unpin" : "Pin" }}
    </button>
  </article>

  <button v-else class="pinned-title-tile" type="button" @click="emit('select', task)">
    <span>{{ task.name }}</span>
  </button>
</template>
