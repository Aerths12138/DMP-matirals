import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const frontendDirectory = path.join(repositoryRoot, 'frontend');
const backendDirectory = path.join(repositoryRoot, 'backend');
const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const pythonCandidates = process.platform === 'win32'
  ? [path.join(repositoryRoot, 'venv', 'Scripts', 'python.exe')]
  : [path.join(repositoryRoot, 'venv', 'bin', 'python')];
const pythonCommand = pythonCandidates.find(existsSync);

function run(command, args, cwd) {
  const result = spawnSync(command, args, {
    cwd,
    stdio: 'inherit',
    shell: false,
  });

  if (result.error) {
    console.error(result.error.message);
    return 1;
  }

  if (result.signal) {
    console.error(`terminated by signal ${result.signal}`);
    return 1;
  }

  return result.status ?? 1;
}

const revisionResult = spawnSync('git', ['rev-parse', '--verify', 'HEAD'], {
  cwd: repositoryRoot,
  encoding: 'utf8',
  shell: false,
});

if (revisionResult.status !== 0) {
  const detail = revisionResult.error?.message || revisionResult.stderr?.trim() || 'unknown error';
  console.error(`Git revision: unavailable (${detail})`);
  process.exit(1);
}

console.log(`Git revision: ${revisionResult.stdout.trim()}`);

if (!pythonCommand) {
  console.error('Backend Python: unavailable (expected venv/Scripts/python.exe or venv/bin/python)');
  process.exit(1);
}

const steps = [
  {
    name: 'Backend tests',
    command: pythonCommand,
    args: ['-m', 'pytest', '-q'],
    cwd: backendDirectory,
  },
  {
    name: 'Frontend typecheck',
    command: npmCommand,
    args: ['exec', '--', 'tsc', '--noEmit'],
    cwd: frontendDirectory,
  },
  {
    name: 'Frontend build',
    command: npmCommand,
    args: ['run', 'build'],
    cwd: frontendDirectory,
  },
  {
    name: 'Frontend focused checks',
    command: npmCommand,
    args: ['run', 'test:assistant-confirmation'],
    cwd: frontendDirectory,
  },
];

const results = [];

for (const [index, step] of steps.entries()) {
  console.log(`\n[${index + 1}/${steps.length}] ${step.name}`);
  const exitCode = run(step.command, step.args, step.cwd);
  results.push({ name: step.name, exitCode });
  console.log(`[${index + 1}/${steps.length}] ${step.name} exit code: ${exitCode}`);
}

console.log('\nAcceptance summary');
for (const result of results) {
  console.log(`- ${result.name}: ${result.exitCode}`);
}

const failedStep = results.find((result) => result.exitCode !== 0);
const overallExitCode = failedStep?.exitCode ?? 0;
console.log(`Overall exit code: ${overallExitCode}`);
process.exit(overallExitCode);
