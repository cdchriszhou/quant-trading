<template>
  <div>
    <el-card shadow="never" style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px">
          <span style="font-weight: bold">大模型接入</span>
          <el-tag size="small" type="info">DeepSeek / GLM / Kimi / 千问</el-tag>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
        title="API Key 仅保存在服务器 .env，前端列表只显示脱敏信息。用于「资金匹配推荐」多模型融合参考（并行调用后共识投票），不替代量化硬过滤。"
      />

      <el-form label-width="120px" style="max-width: 720px" class="responsive-form">
        <el-form-item label="默认提供商">
          <el-radio-group v-model="form.default_provider">
            <el-radio-button
              v-for="p in form.providers"
              :key="p.id"
              :label="p.id"
            >{{ p.name }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card
      v-for="p in form.providers"
      :key="p.id"
      shadow="never"
      style="margin-bottom: 16px"
    >
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: 700">{{ p.name }}</span>
          <el-tag :type="p.api_key_set ? 'success' : 'info'" size="small">
            {{ p.api_key_set ? '已配置 Key' : '未配置' }}
          </el-tag>
        </div>
      </template>

      <el-form label-width="110px" class="responsive-form" style="max-width: 720px">
        <el-form-item label="API Key">
          <el-input
            v-model="p.api_key_input"
            type="password"
            show-password
            clearable
            :placeholder="p.api_key_set ? `已配置：${p.api_key}（留空则不修改）` : '粘贴 API Key'"
            style="max-width: 420px"
          />
          <el-button
            v-if="p.api_key_set"
            text
            type="danger"
            style="margin-left: 8px"
            @click="p.clear_api_key = true; p.api_key_input = ''"
          >清除</el-button>
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="p.base_url" clearable placeholder="OpenAI 兼容地址" />
        </el-form-item>
        <el-form-item label="模型">
          <el-input v-model="p.model" clearable style="max-width: 280px" />
        </el-form-item>
        <el-form-item>
          <el-button :loading="testingId === p.id" @click="handleTest(p.id)">测试连接</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div style="margin-bottom: 24px">
      <el-button type="primary" :loading="saving" @click="handleSave">保存全部配置</el-button>
      <el-button @click="load">刷新</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { adminApi } from '@/api/admin'
import { ElMessage } from 'element-plus'

const saving = ref(false)
const testingId = ref('')
const form = reactive({
  default_provider: 'deepseek',
  providers: [
    { id: 'deepseek', name: 'DeepSeek', api_key: '', api_key_set: false, api_key_input: '', clear_api_key: false, base_url: '', model: '' },
    { id: 'glm', name: '智谱 GLM', api_key: '', api_key_set: false, api_key_input: '', clear_api_key: false, base_url: '', model: '' },
    { id: 'kimi', name: 'Kimi', api_key: '', api_key_set: false, api_key_input: '', clear_api_key: false, base_url: '', model: '' },
    { id: 'qwen', name: '通义千问', api_key: '', api_key_set: false, api_key_input: '', clear_api_key: false, base_url: '', model: '' },
  ],
})

async function load() {
  try {
    const res = await adminApi.getLlmConfig()
    const d = res.data || res
    form.default_provider = d.default_provider || 'deepseek'
    const byId = Object.fromEntries((d.providers || []).map((p) => [p.id, p]))
    for (const p of form.providers) {
      const src = byId[p.id] || {}
      p.name = src.name || p.name
      p.api_key = src.api_key || ''
      p.api_key_set = !!src.api_key_set || !!src.configured
      p.api_key_input = ''
      p.clear_api_key = false
      p.base_url = src.base_url || p.base_url
      p.model = src.model || p.model
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载大模型配置失败')
  }
}

function buildPayload() {
  return {
    default_provider: form.default_provider,
    providers: form.providers.map((p) => ({
      id: p.id,
      base_url: p.base_url,
      model: p.model,
      clear_api_key: !!p.clear_api_key,
      ...(p.api_key_input ? { api_key: p.api_key_input } : {}),
    })),
  }
}

async function handleSave() {
  saving.value = true
  try {
    const res = await adminApi.updateLlmConfig(buildPayload())
    ElMessage.success(res.message || '已保存')
    await load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleTest(providerId) {
  testingId.value = providerId
  try {
    // Persist current form first so test uses latest values
    await adminApi.updateLlmConfig(buildPayload())
    const res = await adminApi.testLlmConnection({ provider: providerId })
    const d = res.data || res
    if (d.ok) ElMessage.success(res.message || '连接成功')
    else ElMessage.warning(res.message || d.message || '连接失败')
    await load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '测试失败')
  } finally {
    testingId.value = ''
  }
}

onMounted(load)
</script>
