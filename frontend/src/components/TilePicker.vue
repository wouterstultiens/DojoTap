<script setup lang="ts">
interface TileOption {
  value: number;
  label: string;
}

const props = withDefaults(
  defineProps<{
  title: string;
  subtitle: string;
  options: TileOption[];
  emptyMessage?: string;
  tileSize?: "small" | "large";
}>(),
  {
    tileSize: "large",
  }
);

const emit = defineEmits<{
  select: [value: number];
  back: [];
}>();
</script>

<template>
  <section class="picker-stage">
    <header class="picker-head">
      <button type="button" class="ghost-btn" @click="emit('back')">Back</button>
      <div class="picker-meta">
        <p class="picker-title">{{ title }}</p>
        <p class="picker-subtitle">{{ subtitle }}</p>
      </div>
      <p class="picker-option-count">{{ options.length }} options</p>
    </header>

    <div
      v-if="options.length > 0"
      class="tile-grid"
      :class="props.tileSize === 'small' ? 'size-small' : 'size-large'"
    >
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
