<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; gap: 10px; flex-wrap: wrap">
      <h3 style="margin: 0">风险控制规则</h3>
      <el-button type="primary" @click="showCreate = true">新增规则</el-button>
    </div>

    <el-card shadow="never">
      <div v-if="rules.length" style="overflow-x: auto; -webkit-overflow-scrolling: touch">
        <el-table :data="rules" stripe size="small">
        <el-table-column prop="name" label="规则名称" width="140" />
        <el-table-column prop="rule_type" label="规则类型" width="130">
          <template #default="{ row }">
            <el-tag>{{ ruleTypeLabel(row.rule_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operator" label="条件" width="70" />
        <el-table-column prop="threshold" label="阈值" width="100" />
        <el-table-column prop="action" label="动作" width="100">
          <template #default="{ row }">
            <el-tag :type="actionType(row.action)" size="small">{{ actionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="70">
          <template #default="{ row }">
            <el-switch v-model="row.is_enabled" @change="toggleRule(row)" />
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button text size="small" type="danger" @click="deleteRule(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      </div>
      <el-empty v-else description="暂无风控规则，建议添加规则保障交易安全" />
    </el-card>

    <el-dialog v-model="showCreate" title="新增风控规则" width="500px">
      <el-form :model="newRule" label-width="100px">
        <el-form-item label="规则名称">
          <el-input v-model="newRule.name" placeholder="如: 单笔交易上限" />
        </el-form-item>
        <el-form-item label="规则类型">
          <el-select v-model="newRule.rule_type" style="width: 100%">
            <el-option label="单笔交易金额" value="order_amount" />
            <el-option label="单品种仓位占比" value="position_pct" />
            <el-option label="持仓数量上限" value="total_stocks" />
            <el-option label="单日最大亏损" value="daily_loss" />
            <el-option label="最大回撤比例" value="drawdown" />
          </el-select>
        </el-form-item>
        <el-form-item label="条件">
          <el-select v-model="newRule.operator" style="width: 100%">
            <el-option label=">" value="gt" />
            <el-option label="<" value="lt" />
            <el-option label=">=" value="ge" />
            <el-option label="<=" value="le" />
            <el-option label="=" value="eq" />
          </el-select>
        </el-form-item>
        <el-form-item label="阈值">
          <el-input-number v-model="newRule.threshold" :min="0" :step="1000" style="width: 200px" />
        </el-form-item>
        <el-form-item label="触发动作">
          <el-select v-model="newRule.action" style="width: 100%">
            <el-option label="仅告警" value="warn" />
            <el-option label="拦截交易" value="block" />
            <el-option label="暂停策略" value="pause_strategy" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newRule.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="createRule" :loading="creating">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { riskApi } from '@/api/risk'
import { ElMessage } from 'element-plus'

const rules = ref([])
const showCreate = ref(false)
const creating = ref(false)
const newRule = reactive({
  name: '', rule_type: 'order_amount', operator: 'le',
  threshold: 100000, action: 'warn', description: '',
  is_enabled: true,
})

const ruleTypeMap = { order_amount: '单笔交易金额', position_pct: '单品种仓位占比', total_stocks: '持仓数量上限', daily_loss: '单日最大亏损', drawdown: '最大回撤比例' }
function ruleTypeLabel(t) { return ruleTypeMap[t] || t }
function actionType(a) { return { warn: 'warning', block: 'danger', pause_strategy: 'info' }[a] || 'info' }
function actionLabel(a) { return { warn: '仅告警', block: '拦截交易', pause_strategy: '暂停策略' }[a] || a }

async function loadRules() {
  try {
    const res = await riskApi.listRules()
    rules.value = res.data || []
  } catch (e) { console.error(e) }
}

async function createRule() {
  creating.value = true
  try {
    await riskApi.createRule({ ...newRule })
    ElMessage.success('规则已创建')
    showCreate.value = false
    await loadRules()
  } catch (e) {
    ElMessage.error('创建失败')
  } finally {
    creating.value = false
  }
}

async function toggleRule(rule) {
  try {
    await riskApi.updateRule(rule.id, { is_enabled: rule.is_enabled })
  } catch (e) {
    rule.is_enabled = !rule.is_enabled
    ElMessage.error('操作失败')
  }
}

async function deleteRule(rule) {
  try {
    await riskApi.deleteRule(rule.id)
    ElMessage.success('已删除')
    await loadRules()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

onMounted(loadRules)
</script>
