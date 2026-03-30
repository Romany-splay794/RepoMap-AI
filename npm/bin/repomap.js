#!/usr/bin/env node
'use strict';

const { spawnSync } = require('child_process');

// Forward every argument after "node bin/repomap.js" to the Python CLI
const args = process.argv.slice(2);

const result = spawnSync('repomap', args, {
  stdio: 'inherit',
  // On Windows, spawn via shell so PATH is resolved correctly
  shell: process.platform === 'win32',
});

if (result.error) {
  if (result.error.code === 'ENOENT') {
    process.stderr.write(
      '[repomap-ai] Could not find the "repomap" Python CLI.\n' +
      '             Try reinstalling: npm install -g repomap-ai\n' +
      '             Or install directly: pip install repomap\n'
    );
    process.exit(1);
  }
  throw result.error;
}

process.exit(result.status ?? 0);
