import assert from 'node:assert/strict';

import {
  canConfirmAssistantAction,
  updateAssistantActionStatus,
} from '../.runtime/validation/actionState.js';
import {
  assistantErrorMessage,
  restoreAssistantConversation,
} from '../.runtime/validation/conversationState.js';

const initial = [
  { token: 'target', status: 'pending', summary: 'Delete a material' },
  { token: 'other', status: 'pending', summary: 'Update a project' },
];

const executing = updateAssistantActionStatus(initial, 'target', 'executing');
assert.equal(executing[0].status, 'executing', 'confirm starts execution');
assert.equal(executing[1], initial[1], 'unrelated actions stay unchanged');

const completed = updateAssistantActionStatus(executing, 'target', 'completed');
assert.equal(completed[0].status, 'completed', 'successful confirmation completes');

const retryable = updateAssistantActionStatus(executing, 'target', 'pending');
assert.equal(retryable[0].status, 'pending', 'failed confirmation becomes retryable');

const cancelled = updateAssistantActionStatus(initial, 'target', 'cancelled');
assert.equal(cancelled[0].status, 'cancelled', 'cancelled actions cannot execute');
assert.equal(canConfirmAssistantAction('pending'), true, 'pending actions can be confirmed');
for (const status of ['executing', 'completed', 'cancelled']) {
  assert.equal(canConfirmAssistantAction(status), false, `${status} actions cannot be confirmed`);
}

let nextId = 0;
const restoredMessages = restoreAssistantConversation(
  [
    { role: 'user', content: '上次的问题' },
    { role: 'assistant', content: '上次的回答' },
  ],
  '欢迎使用',
  () => `message-${nextId += 1}`,
);
assert.deepEqual(
  restoredMessages.map(({ role, content }) => ({ role, content })),
  [
    { role: 'user', content: '上次的问题' },
    { role: 'assistant', content: '上次的回答' },
  ],
  'saved conversation is restored in order',
);
assert.equal(restoredMessages[0].id, 'message-1', 'restored messages receive display ids');

const emptyHistory = restoreAssistantConversation([], '欢迎使用', () => 'welcome');
assert.deepEqual(
  emptyHistory,
  [{ id: 'welcome', role: 'assistant', content: '欢迎使用' }],
  'empty history falls back to the welcome message',
);

assert.equal(
  assistantErrorMessage({ code: 'ECONNABORTED' }),
  '模型处理超过 180 秒，请稍后重试或把长文本分段发送。',
  'client timeout has a specific recovery message',
);
assert.equal(
  assistantErrorMessage({ code: 'ERR_NETWORK' }),
  '无法连接到 AI 服务，请检查后端和网络连接。',
  'network failures are distinct from model failures',
);
assert.equal(
  assistantErrorMessage({ response: { data: { detail: '上游限流' } } }),
  '上游限流',
  'backend error detail remains visible',
);

console.log('AI assistant state: 15 assertions passed');
