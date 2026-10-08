import {
  existsSync,
  lstatSync,
  readFileSync,
  readlinkSync,
} from 'node:fs';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
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
const gitBufferLimit = 64 * 1024 * 1024;

function runGit(args, encoding = 'utf8') {
  const result = spawnSync('git', args, {
    cwd: repositoryRoot,
    encoding,
    maxBuffer: gitBufferLimit,
    shell: false,
  });

  if (result.status !== 0) {
    const detail = result.error?.message || result.stderr?.toString().trim() || 'unknown error';
    throw new Error(detail);
  }

  return result.stdout;
}

function splitNullTerminated(value) {
  return value.split('\0').filter(Boolean);
}

function collectWorkspaceIdentity() {
  const revision = runGit(['rev-parse', '--verify', 'HEAD']).trim();
  const staged = splitNullTerminated(runGit(['diff', '--cached', '--name-only', '-z', '--']));
  const unstaged = splitNullTerminated(runGit(['diff', '--name-only', '-z', '--']));
  const untracked = splitNullTerminated(
    runGit(['ls-files', '--others', '--exclude-standard', '-z']),
  ).sort((left, right) => Buffer.compare(Buffer.from(left), Buffer.from(right)));
  const trackedPatch = runGit([
    'diff',
    '--binary',
    '--full-index',
    '--no-ext-diff',
    '--no-textconv',
    '--no-renames',
    'HEAD',
    '--',
  ], null);

  const hash = createHash('sha256');
  hash.update('materials-dmp-worktree-v1\0');
  hash.update(revision);
  hash.update('\0tracked-patch\0');
  hash.update(trackedPatch);

  for (const route of untracked) {
    const absolutePath = path.join(repositoryRoot, ...route.split('/'));
    const stat = lstatSync(absolutePath);
    hash.update('\0untracked-route\0');
    hash.update(route);
    hash.update('\0type\0');
    hash.update(stat.isSymbolicLink() ? 'symlink' : 'file');
    hash.update('\0content\0');
    hash.update(stat.isSymbolicLink() ? readlinkSync(absolutePath) : readFileSync(absolutePath));
  }

  return {
    revision,
    status: staged.length || unstaged.length || untracked.length ? 'dirty' : 'clean',
    staged: staged.length,
    unstaged: unstaged.length,
    untracked: untracked.length,
    fingerprint: hash.digest('hex'),
  };
}

function run(command, args, cwd) {
  const isWindowsCommandScript = process.platform === 'win32' && command.endsWith('.cmd');
  const executable = isWindowsCommandScript ? (process.env.ComSpec || 'cmd.exe') : command;
  const executableArgs = isWindowsCommandScript
    ? ['/d', '/s', '/c', [command, ...args].join(' ')]
    : args;
  const result = spawnSync(executable, executableArgs, {
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

let workspaceIdentity;
try {
  workspaceIdentity = collectWorkspaceIdentity();
} catch (error) {
  console.error(`Workspace identity: unavailable (${error.message})`);
  process.exit(1);
}

console.log(`Git revision: ${workspaceIdentity.revision}`);
console.log(
  `Workspace status: ${workspaceIdentity.status} `
  + `(staged: ${workspaceIdentity.staged}, unstaged: ${workspaceIdentity.unstaged}, `
  + `untracked: ${workspaceIdentity.untracked})`,
);
console.log(`Workspace fingerprint: sha256:${workspaceIdentity.fingerprint}`);

if (process.argv.includes('--identity-only')) {
  console.log('Identity-only mode: acceptance checks skipped.');
  process.exit(0);
}

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
  {
    name: 'Frontend assistant Excel flow',
    command: npmCommand,
    args: ['run', 'test:assistant-excel'],
    cwd: frontendDirectory,
  },
  {
    name: 'Frontend import normalization (test:import-normalization)',
    command: npmCommand,
    args: ['run', 'test:import-normalization'],
    cwd: frontendDirectory,
  },
  {
    name: 'Frontend import alignment flow',
    command: npmCommand,
    args: ['run', 'test:import-alignment-flow'],
    cwd: frontendDirectory,
  },
  {
    name: 'Frontend import quality demo fixtures',
    command: npmCommand,
    args: ['run', 'test:import-quality'],
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
