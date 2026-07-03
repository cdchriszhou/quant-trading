<template>
  <router-view />
</template>

<script setup>
</script>

<style>
/* ============================================================
   GoPro-Inspired Light Theme — Clean, modern, professional
   ============================================================ */

:root {
  --gp-cyan: #00B4B4;
  --gp-cyan-light: rgba(0, 180, 180, 0.08);
  --gp-blue: #1A6FF5;
  --gp-text: #1a1a1a;
  --gp-text-secondary: #6b7280;
  --gp-border: #e5e7eb;
  --gp-bg: #f5f6f8;
  --gp-card-bg: #ffffff;
  --gp-radius: 10px;
}

html, body, #app {
  height: 100%;
  margin: 0;
  padding: 0;
  background: var(--gp-bg);
  color: var(--gp-text);
  -webkit-tap-highlight-color: transparent;
}

/* ----- Responsive ----- */
@media (max-width: 767px) {
  .el-table {
    font-size: 12px !important;
  }
  .el-table th.el-table__cell {
    font-size: 11px !important;
    padding: 8px 4px !important;
  }
  .el-table td.el-table__cell {
    padding: 6px 4px !important;
  }
  .el-card__header {
    padding: 12px 14px !important;
  }
  .el-card__body {
    padding: 12px 14px !important;
  }
  .el-main {
    padding: 8px !important;
  }
  .el-message {
    min-width: auto !important;
    max-width: 90vw !important;
  }
  .el-form-item__label {
    font-size: 13px !important;
  }
  .el-dialog {
    width: 92vw !important;
    margin-top: 10vh !important;
  }
  .el-breadcrumb {
    font-size: 12px !important;
  }
  .el-radio-button__inner {
    padding: 6px 10px !important;
    font-size: 12px !important;
  }
  .responsive-descriptions .el-descriptions__body .el-descriptions__table {
    display: block;
  }
  .responsive-descriptions .el-descriptions__body .el-descriptions__row {
    display: flex;
    flex-wrap: wrap;
  }
  .responsive-descriptions .el-descriptions__body .el-descriptions__cell {
    flex: 1 1 100%;
    min-width: 0;
  }
  .responsive-form .el-form-item__label {
    float: none !important;
    display: block !important;
    text-align: left !important;
    padding-bottom: 4px;
  }
  .responsive-form .el-form-item__content {
    margin-left: 0 !important;
  }
  .el-select,
  .el-input-number {
    max-width: 100%;
  }
}

@media (min-width: 768px) and (max-width: 1023px) {
  .el-main {
    padding: 12px !important;
  }
  .responsive-descriptions .el-descriptions__body .el-descriptions__cell {
    flex: 1 1 50%;
  }
}

/* ----- Element Plus overrides ----- */
:root {
  --el-color-primary: var(--gp-cyan);
  --el-color-primary-light-3: #33C8C8;
  --el-color-primary-light-5: #66D8D8;
  --el-color-primary-light-7: #99E8E8;
  --el-color-primary-light-9: #CCF5F5;
  --el-color-success: #10b981;
  --el-color-danger: #ef4444;
  --el-color-warning: #f59e0b;
  --el-border-radius-base: 6px;
}

.el-card {
  border-radius: var(--gp-radius) !important;
  border: 1px solid var(--gp-border) !important;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}
.el-card__header {
  font-weight: 600;
  border-bottom: 1px solid var(--gp-border) !important;
}

.el-button--primary {
  font-weight: 600 !important;
  letter-spacing: 0.3px;
}

.el-menu {
  border-right: none !important;
}
.el-menu-item.is-active {
  color: var(--gp-cyan) !important;
  background: var(--gp-cyan-light) !important;
}

.el-table th.el-table__cell {
  background: #f9fafb !important;
  color: var(--gp-text-secondary) !important;
  font-weight: 600 !important;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
</style>
