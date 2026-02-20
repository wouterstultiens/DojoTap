<script setup lang="ts">
defineProps<{
  cohort: string;
  category: string;
  search: string;
  pinnedOnly: boolean;
  hideCompleted: boolean;
  cohortOptions: string[];
  categoryOptions: string[];
}>();

const emit = defineEmits<{
  updateCohort: [value: string];
  updateCategory: [value: string];
  updateSearch: [value: string];
  updatePinnedOnly: [value: boolean];
  updateHideCompleted: [value: boolean];
  refresh: [];
}>();
</script>

<template>
  <section class="filters">
    <label>
      Cohort
      <select
        :value="cohort"
        @change="emit('updateCohort', ($event.target as HTMLSelectElement).value)"
      >
        <option value="ALL">All</option>
        <option v-for="option in cohortOptions" :key="option" :value="option">
          {{ option }}
        </option>
      </select>
    </label>

    <label>
      Category
      <select
        :value="category"
        @change="emit('updateCategory', ($event.target as HTMLSelectElement).value)"
      >
        <option value="ALL">All</option>
        <option v-for="option in categoryOptions" :key="option" :value="option">
          {{ option }}
        </option>
      </select>
    </label>

    <label class="search-wrap">
      Search
      <input
        :value="search"
        @input="emit('updateSearch', ($event.target as HTMLInputElement).value)"
        type="search"
        placeholder="Task name"
      />
    </label>

    <label class="check-wrap">
      <input
        type="checkbox"
        :checked="pinnedOnly"
        @change="emit('updatePinnedOnly', ($event.target as HTMLInputElement).checked)"
      />
      Pinned
    </label>

    <label class="check-wrap">
      <input
        type="checkbox"
        :checked="hideCompleted"
        @change="emit('updateHideCompleted', ($event.target as HTMLInputElement).checked)"
      />
      Hide completed
    </label>

    <button class="ghost-btn" type="button" @click="emit('refresh')">Refresh</button>
  </section>
</template>
