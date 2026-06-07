<template>
  <div class="section-title">
    <div class="section-title__bar"></div>
    <div class="section-title__text">
      <h3>{{ title }}</h3>
      <span v-if="subtitle">{{ subtitle }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
})
</script>

<style scoped>
.section-title {
  display: flex; align-items: center; gap: 12px;
  margin: 20px 0 14px;
}
.section-title__bar {
  width: 4px; height: 22px;
  background: linear-gradient(180deg, var(--primary) 0%, #69c0ff 100%);
  border-radius: 2px; flex-shrink: 0;
}
.section-title__text { display: flex; align-items: baseline; gap: 10px; }
.section-title__text h3 { margin: 0; font-size: 15px; font-weight: 600; color: var(--text); }
.section-title__text span { font-size: 12px; color: var(--text-secondary); }
</style>
