<script setup lang="ts">
interface TileOption {
  value: number;
  label: string;
}

defineProps<{
  title: string;
  subtitle: string;
  options: TileOption[];
  emptyMessage?: string;
}>();

const emit = defineEmits<{
  select: [value: number];
  back: [];
}>();
</script>

<template>
  <section class="picker-stage">
    <header class="picker-head">
      <button type="button" class="ghost-btn" @click="emit('back')">Back</button>
      <div>
        <p class="picker-title">{{ title }}</p>
        <p class="picker-subtitle">{{ subtitle }}</p>
      </div>
    </header>

    <div v-if="options.length > 0" class="tile-grid">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        class="input-tile"
        :data-testid="`${title.toLowerCase()}-tile-${option.value}`"
        @click="emit('select', option.value)"
      >
        {{ option.label }}
      </button>
    </div>

    <p v-else class="empty-state">{{ emptyMessage || "No options available for this setup." }}</p>
  </section>
</template>
