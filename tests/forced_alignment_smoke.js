// Keep audio-derived Enhanced LRC times and reject stale song UI updates.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/app.js','utf8');
const ids=['force-align','force-state','force-language','ref-lyrics','lrc'];
const elements=Object.fromEntries(ids.map(id=>[id,{value:'',disabled:false,textContent:''}]));
elements['ref-lyrics'].value='正確歌詞';elements['force-language'].value='zh';
const lrc='[00:01.20]<00:01.20>正<00:01.80>確<00:02.50>歌<00:03.20>詞\n';
const state={song:{id:'abcdef'},showLyr:true};let parsed,switched=false;
const context=vm.createContext({S:state,$:selector=>elements[selector.slice(1)],
  api:async(path,opts)=>{if(path.endsWith('/force-align')){assert.equal(opts.json.text,'正確歌詞');return {job:'alignment'};}return {lrc};},
  waitJob:async(id,onStep)=>{onStep({step:'done',progress:1});if(switched)state.song={id:'different'};},
  toast(){},store:{set(){}},syncLyrButtons(){},pollJobs(){},
  setLines:text=>{parsed=text;},commitLines(){throw Error('must not overwrite forced times');},
});
vm.runInContext(source.slice(source.indexOf('const CJK ='),source.indexOf('/* 依旋律音符')),context);
const start=source.indexOf('$("#force-align").onclick');const end=source.indexOf('/* 匯出歌詞',start);
vm.runInContext(source.slice(start,end),context);
(async()=>{
 await elements['force-align'].onclick();assert.equal(parsed,lrc);assert.equal(elements['force-align'].disabled,false);
 const lines=context.parseLrc(lrc);assert.deepEqual(Array.from(lines[0].chars,u=>u.t),[1.2,1.8,2.5,3.2]);
 assert.ok(vm.runInContext('toLrc(parseLrc('+JSON.stringify(lrc)+'))',context).includes('<00:03.20>詞'));
 parsed=null;switched=true;await elements['force-align'].onclick();assert.equal(parsed,null,'switched song must not receive old alignment');
 console.log('Forced alignment submit, progress, Enhanced LRC preservation and song-switch guard passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
