const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync('static/app.js', 'utf8');
const start = source.indexOf('cv.addEventListener("pointermove"');
const end = source.indexOf('cv.addEventListener("pointerup"', start);
function fixture() {
  const listeners = {};
  const lines = [{t: 1}, {t: 5, chars: [{t: 5}, {t: 6}]}, {t: 10}];
  const state = {lines, zoom: 10, dirty: false, playing: true};
  const drag = {kind: 'char', line: lines[1], i: 0, G: {W: 200}, startX: 10, t0: 5};
  const context = vm.createContext({S: state, drag, KEYW: 100, cv: {addEventListener: (n, fn) => listeners[n] = fn},
    clamp: (n, lo, hi) => Math.max(lo, Math.min(hi, n)), geom: () => ({tx: x => x / 10})});
  vm.runInContext(source.slice(start, end), context);
  return {listeners, state, drag, context};
}
test('per-character dragging still respects adjacent lines and characters', () => {
  const {listeners, state} = fixture();
  listeners.pointermove({offsetX: 0});
  assert.equal(state.lines[1].chars[0].t, 4);
  assert.equal(state.lines[1].t, 4);
  listeners.pointermove({offsetX: -100});
  assert.equal(state.lines[1].t, 1.1);
  assert.equal(state.dirty, true);
});
test('whole-line dragging during playback moves character timing together', () => {
  const {state, drag, context} = fixture();
  drag.kind = 'line';
  context.dragLineTo(8);
  assert.equal(state.lines[1].t, 8);
  assert.deepEqual(state.lines[1].chars.map(c => c.t), [8, 9]);
  context.dragLineTo(12);
  assert.equal(state.lines[1].t, 9.9);
});
