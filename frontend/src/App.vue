<template>
  <router-view />
</template>

<script setup>
</script>

<style>
:root {
  --primary: #1890ff;
  --primary-dark: #096dd9;
  --success: #52c41a;
  --warning: #fa8c16;
  --danger: #ff4d4f;
  --bg: #f0f2f5;
  --card-bg: #ffffff;
  --text: #262626;
  --text-secondary: #8c8c8c;
  --border: #f0f0f0;
  --shadow: 0 2px 8px rgba(0,0,0,.06);
  --shadow-hover: 0 4px 16px rgba(0,0,0,.1);
  --radius: 10px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif; background: var(--bg); color: var(--text); -webkit-font-smoothing: antialiased; }

/* 全局卡片 */
.el-card {
  border-radius: var(--radius) !important;
  border: 1px solid var(--border) !important;
  box-shadow: var(--shadow) !important;
  transition: box-shadow .3s;
}
.el-card:hover { box-shadow: var(--shadow-hover) !important; }

/* 卡片标题 */
.el-card__header {
  padding: 14px 20px !important;
  border-bottom: 1px solid var(--border) !important;
  font-weight: 600;
  font-size: 14px;
  color: var(--text);
  background: #fafafa;
  border-radius: var(--radius) var(--radius) 0 0 !important;
}

/* 全局滚动条 */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #d9d9d9; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #bfbfbf; }

/* 表格优化 */
.el-table { border-radius: var(--radius); overflow: hidden; }
.el-table th.el-table__cell { background: #fafafa; color: var(--text); font-weight: 600; }

/* 按钮 */
.el-button--primary { background: var(--primary); border-color: var(--primary); }
.el-button--primary:hover { background: var(--primary-dark); border-color: var(--primary-dark); }
.el-button.is-link { font-weight: 500; }

/* 标签 */
.el-tag--plain { border-color: #d9d9d9; }

/* 图表卡片内容区 */
.el-card .el-card__body { padding: 16px 20px; }
</style>
