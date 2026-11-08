const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/app.js', 'utf8');
const start = source.indexOf('function queueAtEnd()');
const part = source.slice(start, source.indexOf('/* 前奏倒數', start));
function fixture() {
  const callbacks = [], state = {song: {id:'ended'}, playing:false}, live = {on:true, queue:['next']};
  let advances = 0;
  const context = vm.createContext({S:state,LIVE:live,setTimeout:fn=>callbacks.push(fn),queueNext:()=>advances++});
  vm.runInContext('let songOpenRequest = 1;\n' + part, context);
  context.queueAtEnd();
  return {callbacks,state,live,context,advances:()=>advances};
}
test('a completed song loads the queued song once after the delay',()=>{
  const f = fixture(); assert.equal(f.advances(),0); f.callbacks[0](); assert.equal(f.advances(),1);
});
test('a new external selection, new request for the same song, playback or leaving live mode cancels delayed advance',()=>{
  for (const change of [f=>{f.state.song={id:'external'};}, f=>vm.runInContext('songOpenRequest++',f.context),
                         f=>{f.state.playing=true;}, f=>{f.live.on=false;}]) {
    const f = fixture(); change(f); f.callbacks[0](); assert.equal(f.advances(),0);
  }
});
