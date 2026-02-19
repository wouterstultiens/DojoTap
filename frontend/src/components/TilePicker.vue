<script setup lang="ts">
interface TileOption {
  value: number;
  label: string;
}

defineProps<{
  title: string;
  subtitle: string;
  options: TileOption[];
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

    <div class="tile-grid">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        class="input-tile"
        @click="emit('select', option.value)"
      >
        {{ option.label }}
      </button>
    </div>
  </section>
</template>
