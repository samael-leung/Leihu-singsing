const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync('static/app.js','utf8');
test('playlist-only processing shows the global pause control and paused state shows resume',()=>{
  const elements = Object.fromEntries(['jobs-paused','jobs-bar','jobs-sum'].map(id=>[id,{}]));
  const context = vm.createContext({$:selector=>elements[selector.slice(1)]});
  const start=source.indexOf('function syncPauseBar('),end=source.indexOf('let liveHoldWas',start);
  vm.runInContext('let pausedNow=false;\n'+source.slice(start,end),context);
  context.syncPauseBar({live:{paused:false},jobs:[{kind:'playlist',status:'queued'},{kind:'playlist',status:'running'}]});
  assert.equal(elements['jobs-bar'].hidden,false);
  assert.equal(elements['jobs-sum'].textContent,'處理中 1 首、排隊 1 首');
  context.syncPauseBar({live:{paused:true},jobs:[{kind:'playlist',status:'queued'}]});
  assert.equal(elements['jobs-bar'].hidden,true);assert.equal(elements['jobs-paused'].hidden,false);
});
