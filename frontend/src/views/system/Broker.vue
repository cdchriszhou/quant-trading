<template>
  <div>
    <el-card shadow="never" style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px">
          <span style="font-weight: bold">实盘接入（MiniQMT）</span>
          <el-tag :type="statusTagType" size="small">{{ statusText }}</el-tag>
        </div>
      </template>

      <el-alert
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
        title="开启实盘后，顶栏「真实账户」与策略实盘模式将走 MiniQMT 真实下单。请确认已登录 MiniQMT / 投研端。"
      />

      <el-form ref="formRef" :model="form" label-width="140px" style="max-width: 640px" class="responsive-form">
        <el-form-item label="启用实盘交易">
          <el-switch v-model="form.allow_live_trading" active-text="开" inactive-text="关" />
        </el-form-item>
        <el-form-item label="券商通道">
          <el-select v-model="form.broker_type" style="width: 220px">
            <el-option label="MiniQMT (xtquant)" value="qmt" />
          </el-select>
        </el-form-item>
        <el-form-item label="MiniQMT 路径">
          <el-input
            v-model="form.qmt_mini_path"
            placeholder="例如 D:/国金证券QMT交易端/userdata_mini"
            clearable
          />
          <div style="font-size: 12px; color: #909399; margin-top: 4px">
            指向 MiniQMT 的 userdata_mini 目录（不是安装根目录）
          </div>
        </el-form-item>
        <el-form-item label="资金账号">
          <el-input v-model="form.qmt_account_id" placeholder="券商资金账号" clearable style="max-width: 280px" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSave">保存配置</el-button>
          <el-button :loading="testing" @click="handleTest">测试连接</el-button>
          <el-button @click="load">刷新状态</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <template #header><span style="font-weight: bold">连接详情</span></template>
      <el-descriptions :column="2" border size="small" class="responsive-descriptions">
        <el-descriptions-item label="通道">{{ status.broker || '—' }}</el-descriptions-item>
        <el-descriptions-item label="连接状态">
          <el-tag :type="status.connected ? 'success' : 'info'" size="small">
            {{ status.connected ? '已连接' : '未连接' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="资金账号">{{ status.account_id || form.qmt_account_id || '—' }}</el-descriptions-item>
        <el-descriptions-item label="可用资金">
          {{ status.cash != null ? `¥${Number(status.cash).toLocaleString()}` : '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="说明" :span="2">{{ status.message || '—' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { adminApi } from '@/api/admin'
import { useAccountStore } from '@/stores/account'
import { ElMessage } from 'element-plus'

const accountStore = useAccountStore()
const saving = ref(false)
const testing = ref(false)
const status = ref({})

const form = reactive({
  allow_live_trading: false,
  broker_type: 'qmt',
  qmt_mini_path: '',
  qmt_account_id: '',
})

const statusText = computed(() => {
  if (!form.allow_live_trading) return '实盘已关闭'
  if (status.value?.connected) return 'MiniQMT 已连接'
  return status.value?.message || '实盘未连接'
})

const statusTagType = computed(() => {
  if (!form.allow_live_trading) return 'info'
  return status.value?.connected ? 'success' : 'warning'
})

async function load() {
  try {
    const res = await adminApi.getBrokerConfig()
    const d = res.data || res
    form.allow_live_trading = !!d.allow_live_trading
    form.broker_type = d.broker_type || 'qmt'
    form.qmt_mini_path = d.qmt_mini_path || ''
    form.qmt_account_id = d.qmt_account_id || ''
    status.value = d.status || {}
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载配置失败')
  }
}

async function handleSave() {
  saving.value = true
  try {
    const res = await adminApi.updateBrokerConfig({
      allow_live_trading: form.allow_live_trading,
      broker_type: form.broker_type,
      qmt_mini_path: form.qmt_mini_path,
      qmt_account_id: form.qmt_account_id,
    })
    const d = res.data || res
    status.value = d.status || {}
    ElMessage.success(res.message || '已保存')
    await accountStore.refresh()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleTest() {
  testing.value = true
  try {
    // Save first so test uses latest form values
    await adminApi.updateBrokerConfig({
      allow_live_trading: form.allow_live_trading,
      broker_type: form.broker_type,
      qmt_mini_path: form.qmt_mini_path,
      qmt_account_id: form.qmt_account_id,
    })
    const res = await adminApi.testBrokerConnection()
    status.value = res.data?.status || res.status || {}
    if (status.value.connected) {
      ElMessage.success(res.message || '连接成功')
    } else {
      ElMessage.warning(res.message || status.value.message || '连接失败')
    }
    await accountStore.refresh()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '测试失败')
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>
