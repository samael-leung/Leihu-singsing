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
    if (record.originalBridge) fs.copyFileSync(path.join(backup, 'leihu-selection-compat.js'), bridge);
    else fs.unlinkSync(bridge);
    if (record.originalMarker) fs.copyFileSync(path.join(backup, 'repair-record.json'), marker);
    else fs.unlinkSync(marker);
    console.log('Original index.js restored. Existing leihu.js, queue.js and settings were not changed.');
    return;
  }
  const original = fs.readFileSync(target, 'utf8');
  const mounts = original.match(/require\(\s*['"]\.\/leihu-selection-compat['"]\s*\)\s*\(\s*app\s*\)\s*;/g) || [];
  if (mounts.length > 1 || (!mounts.length && original.includes('/api/integrations/leihu/selection'))) {
    throw new Error('Another selection API is already present. No files changed.');
  }
  const suppliedBridge = path.join(__dirname, 'leihu-selection-compat.js');
  const previousBridge = fs.existsSync(bridge) ? fs.readFileSync(bridge) : null;
  const previousMarker = fs.existsSync(marker) ? fs.readFileSync(marker) : null;
  const known = [sha(suppliedBridge), '0e0e66959677276e59769cba61e3f3e03b073c3f868e666aa3d3c951115ac4c3'];
  if (previousBridge && !known.includes(sha(bridge))) throw new Error('The existing bridge has custom edits. No files changed.');
  if (mounts.length && previousBridge && sha(bridge) === sha(suppliedBridge)) {
    console.log('The current repair is already installed. Restart the song-request server and verify the selection URL.');
    return;
  }
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
  check(target); check(suppliedBridge);
  const newline = original.includes('\r\n') ? '\r\n' : '\n';
  const patched = mounts.length ? original : original.slice(0, anchor.index) + "require('./leihu-selection-compat')(app);" + newline + original.slice(anchor.index);
  const backup = path.join(root, 'backups', `leihu-sync-${new Date().toISOString().replace(/[:.]/g, '-')}-${crypto.randomBytes(3).toString('hex')}`);
  fs.mkdirSync(backup, { recursive: true });
  fs.copyFileSync(target, path.join(backup, 'index.js'));
  if (previousBridge) fs.writeFileSync(path.join(backup, 'leihu-selection-compat.js'), previousBridge);
  if (previousMarker) fs.writeFileSync(path.join(backup, 'repair-record.json'), previousMarker);
  const staging = path.join(server, `.leihu-sync-${crypto.randomBytes(4).toString('hex')}.js`);
  let replaced = false;
  try {
    fs.writeFileSync(staging, patched, 'utf8'); check(staging);
    fs.copyFileSync(suppliedBridge, bridge);
    fs.renameSync(staging, target); replaced = true;
    fs.writeFileSync(marker, JSON.stringify({ backup: path.relative(root, backup), patchedHash: sha(target), bridgeHash: sha(bridge),
      originalBridge: !!previousBridge, originalMarker: !!previousMarker }, null, 2));
  } catch (error) {
    if (replaced) fs.copyFileSync(path.join(backup, 'index.js'), target);
    if (previousBridge) fs.writeFileSync(bridge, previousBridge);
    else if (fs.existsSync(bridge)) fs.unlinkSync(bridge);
    if (previousMarker) fs.writeFileSync(marker, previousMarker);
    else if (fs.existsSync(marker)) fs.unlinkSync(marker);
    throw error;
  } finally { if (fs.existsSync(staging)) fs.unlinkSync(staging); }
  console.log(`Repair installed. Backup: ${backup}`);
  console.log('Preserved: server/leihu.js, server/queue.js, .env, song-links.json, dependencies.');
  console.log('Start npm start, then GET http://127.0.0.1:3000/api/integrations/leihu/selection');
}
try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
