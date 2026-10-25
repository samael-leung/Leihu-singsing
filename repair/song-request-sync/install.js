'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const root = path.resolve(process.argv[2] || '.');
const server = path.join(root, 'server');
const target = path.join(server, 'index.js');
const bridge = path.join(server, 'leihu-selection-compat.js');
const undo = process.argv.includes('--undo');
function check(file) {
  const result = spawnSync(process.execPath, ['--check', file], { encoding: 'utf8', windowsHide: true });
  if (result.status !== 0) throw new Error(`Syntax check failed: ${result.stderr || result.error || file}`);
}
function sha(file) { return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'); }
function main() {
  for (const name of ['package.json', 'server/index.js', 'server/queue.js', 'server/leihu.js']) {
    if (!fs.existsSync(path.join(root, name))) throw new Error(`Project file not found: ${name}`);
  }
  const marker = path.join(root, '.leihu-sync-repair.json');
  if (undo) {
    if (!fs.existsSync(marker)) throw new Error('No repair record found. No files changed.');
    const record = JSON.parse(fs.readFileSync(marker, 'utf8'));
    if (sha(target) !== record.patchedHash || !fs.existsSync(bridge) || sha(bridge) !== record.bridgeHash) {
      throw new Error('Files changed after the repair; refusing to overwrite later edits. Restore manually from the backup.');
    }
    const backup = path.resolve(root, record.backup);
    if (!backup.startsWith(path.join(root, 'backups') + path.sep)) throw new Error('Invalid backup path');
    fs.copyFileSync(path.join(backup, 'index.js'), target);
    fs.unlinkSync(bridge); fs.unlinkSync(marker);
    console.log('Original index.js restored. Existing leihu.js, queue.js and settings were not changed.');
    return;
  }
  const original = fs.readFileSync(target, 'utf8');
  if (original.includes('/api/integrations/leihu/selection') || original.includes("require('./leihu-selection-compat')")) {
    throw new Error('A selection API is already present. No files changed.');
  }
  if (fs.existsSync(bridge) || fs.existsSync(marker)) throw new Error('An existing repair file was found. No files changed.');
  const queueSource = fs.readFileSync(path.join(server, 'queue.js'), 'utf8');
  if (!/function\s+moveSong\s*\(\s*fromZone\s*,\s*fromIndex\s*,\s*toZone\s*,/.test(queueSource)) {
    throw new Error('Unrecognized moveSong interface. No files changed; provide server/queue.js for review.');
  }
  for (const name of ['getState', 'addSong', 'broadcastRaw']) {
    if (!new RegExp('function\\s+' + name + '\\s*\\(').test(queueSource)) throw new Error(`Unrecognized queue interface: ${name}. No files changed.`);
  }
  if (!/setLink/.test(fs.readFileSync(path.join(server, 'leihu.js'), 'utf8'))) throw new Error('Unrecognized existing Leihu module. No files changed.');
  const anchor = /^([ \t]*)app\.get\(\s*['"]\/api\/leihu\/status['"]/m.exec(original);
  if (!anchor) throw new Error('Existing /api/leihu/status route not found. No files changed.');
  check(target); check(path.join(__dirname, 'leihu-selection-compat.js'));
  const newline = original.includes('\r\n') ? '\r\n' : '\n';
  const patched = original.slice(0, anchor.index) + "require('./leihu-selection-compat')(app);" + newline + original.slice(anchor.index);
  const backup = path.join(root, 'backups', `leihu-sync-${new Date().toISOString().replace(/[:.]/g, '-')}-${crypto.randomBytes(3).toString('hex')}`);
  fs.mkdirSync(backup, { recursive: true });
  fs.copyFileSync(target, path.join(backup, 'index.js'));
  const staging = path.join(server, `.leihu-sync-${crypto.randomBytes(4).toString('hex')}.js`);
  let replaced = false;
  try {
    fs.writeFileSync(staging, patched, 'utf8'); check(staging);
    fs.copyFileSync(path.join(__dirname, 'leihu-selection-compat.js'), bridge);
    fs.renameSync(staging, target); replaced = true;
    fs.writeFileSync(marker, JSON.stringify({ backup: path.relative(root, backup), patchedHash: sha(target), bridgeHash: sha(bridge) }, null, 2));
  } catch (error) {
    if (replaced) fs.copyFileSync(path.join(backup, 'index.js'), target);
    if (fs.existsSync(bridge)) fs.unlinkSync(bridge);
    if (fs.existsSync(marker)) fs.unlinkSync(marker);
    throw error;
  } finally { if (fs.existsSync(staging)) fs.unlinkSync(staging); }
  console.log(`Repair installed. Backup: ${backup}`);
  console.log('Preserved: server/leihu.js, server/queue.js, .env, song-links.json, dependencies.');
  console.log('Start npm start, then GET http://127.0.0.1:3000/api/integrations/leihu/selection');
}
try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
