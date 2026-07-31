import assert from 'node:assert/strict';

import {
  canConfirmAssistantAction,
  updateAssistantActionStatus,
} from '../.runtime/validation/actionState.js';

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

console.log('AI assistant confirmation state: 9 assertions passed');
