// Exercise the shipped mic lifecycle with different capture/playback clocks.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const js = fs.readFileSync('static/app.js', 'utf8');
const contexts = [], timers = [], elements = {};
const element = id => elements[id] ||= {value:'',classList:{add(){},remove(){}}};
let stopped = 0, detectedRate, gainTime;
class AudioContext {
  constructor() { this.sampleRate=contexts.length ? 48000 : 44100; this.currentTime=contexts.length ? 20 : 7; this.closed=false; contexts.push(this); }
  resume() {}
  close() { this.closed=true; return Promise.resolve(); }
  node() { return {connect(){},disconnect(){}}; }
  createMediaStreamSource() { return this.node(); }
  createAnalyser() { return {...this.node(),getFloatTimeDomainData(){}}; }
  createGain() { return {...this.node(),gain:{setTargetAtTime(value,time){gainTime=time;}}}; }
  createDynamicsCompressor() { return {...this.node(),...Object.fromEntries(['threshold','knee','ratio','attack','release'].map(k=>[k,{}]))}; }
  createMediaStreamDestination() { return {stream:{}}; }
}
const state={micGain:1,playing:true,speed:1,live:[]};
const context=vm.createContext({window:{AudioContext},S:state,$:element,
 navigator:{mediaDevices:{getUserMedia:async()=>({getTracks:()=>[{stop(){stopped++;}}],getAudioTracks:()=>[{label:'USB mic'}]})}},
 listMics(){},toast(message){throw Error(message);},micLevel(){},recTap:async()=>null,
 detect(buf,rate){detectedRate=rate;return 60;},cur:()=>10,keyHintAdd(){},refAt(){},
 setTimeout(fn,delay){assert.equal(delay,1500);timers.push(fn);},
 stopRecording(){state.rec=null;},store:{get:()=>1},
});
vm.runInContext(js.slice(js.indexOf('let ctx ='),js.indexOf('/* ------------------------------------------------------------ 導覽')),context);
vm.runInContext(js.slice(js.indexOf('async function startMic()'),js.indexOf('/* 麥克風音量表')),context);
vm.runInContext(js.slice(js.indexOf('function syncGainUi()'),js.indexOf('function setMicGain(')),context);
(async()=>{
 const playback=vm.runInContext('ac()',context);
 await context.startMic();
 assert.equal(contexts.length,2);
 const capture=contexts[1];assert.notEqual(playback,capture);
 context.micFrame();context.micFrame();
 assert.equal(detectedRate,48000);
 assert.equal(state.live[0].t,10-2048/2/48000);
 context.syncGainUi();assert.equal(gainTime,20);
 state.rec={};context.stopMic();assert.equal(state.rec,null);assert.equal(stopped,1);
 assert.equal(playback.closed,false);assert.equal(capture.closed,false);
 await context.startMic();const replacement=contexts[2];
 timers.shift()();assert.equal(capture.closed,true);assert.equal(replacement.closed,false);assert.equal(playback.closed,false);
 context.stopMic();timers.shift()();assert.equal(replacement.closed,true);
 console.log('USB mic: independent clocks, pitch timing, gain, recording stop and delayed close passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
