#!/usr/bin/env node
'use strict';

const { execSync, spawnSync } = require('child_process');

const PYPI_PACKAGE = 'repomap-ai';
const MIN_PYTHON_VERSION = [3, 11];

// ─── Helpers ────────────────────────────────────────────────────────────────

function log(msg) {
  process.stdout.write('[repomap-ai] ' + msg + '\n');
}

function err(msg) {
  process.stderr.write('[repomap-ai] ERROR: ' + msg + '\n');
}

/** Try running a command; return stdout on success, null on failure. */
function tryExec(cmd) {
  try {
    return execSync(cmd, { stdio: ['ignore', 'pipe', 'ignore'] })
      .toString()
      .trim();
  } catch {
    return null;
  }
}

// ─── Check if repomap CLI is already on PATH ─────────────────────────────────

const alreadyInstalled = tryExec('repomap --version');
if (alreadyInstalled !== null) {
  log('repomap is already installed (' + alreadyInstalled + '). Nothing to do.');
  process.exit(0);
}

// ─── Detect Python ───────────────────────────────────────────────────────────

function detectPython() {
  for (const bin of ['python3', 'python']) {
    const version = tryExec(bin + ' --version');
    if (!version) continue;

    // version looks like "Python 3.12.0"
    const match = version.match(/Python (\d+)\.(\d+)/);
    if (!match) continue;

    const major = parseInt(match[1], 10);
    const minor = parseInt(match[2], 10);
    if (
      major > MIN_PYTHON_VERSION[0] ||
      (major === MIN_PYTHON_VERSION[0] && minor >= MIN_PYTHON_VERSION[1])
    ) {
      return bin;
    }
  }
  return null;
}

const python = detectPython();
if (!python) {
  err(
    'Python 3.11 or later is required but was not found on your PATH.\n' +
    '       Install Python from https://python.org/downloads/ and then re-run:\n' +
    '         npm install -g repomap-ai'
  );
  process.exit(1);
}

log('Found ' + tryExec(python + ' --version') + '. Installing repomap from PyPI…');

// ─── Detect pip ──────────────────────────────────────────────────────────────

function detectPip(pythonBin) {
  // Prefer running pip as a Python module to guarantee it matches the right interpreter
  if (tryExec(pythonBin + ' -m pip --version') !== null) {
    return pythonBin + ' -m pip';
  }
  for (const bin of ['pip3', 'pip']) {
    if (tryExec(bin + ' --version') !== null) return bin;
  }
  return null;
}

const pip = detectPip(python);
if (!pip) {
  err(
    'pip was not found. Install pip by running:\n' +
    '         ' + python + ' -m ensurepip --upgrade\n' +
    '       then re-run:\n' +
    '         npm install -g repomap-ai'
  );
  process.exit(1);
}

// ─── Install repomap ─────────────────────────────────────────────────────────

const result = spawnSync(
  pip.split(' ')[0],
  [...pip.split(' ').slice(1), 'install', '--upgrade', PYPI_PACKAGE],
  { stdio: 'inherit' }
);

if (result.status !== 0) {
  err(
    'pip install failed. You can install manually with:\n' +
    '         pip install repomap\n' +
    '       then re-run your command.'
  );
  process.exit(result.status || 1);
}

log('repomap installed successfully! Run: repomap generate .');
