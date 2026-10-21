// Switching between songs with identical lyrics must resend lines to the overlay.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('static/app.js','utf8');
const part=source.slice(source.indexOf('const OV ='),source.indexOf('/* 直播歌詞設定視窗 */'));
const sent=[]; let now=0;
const state={song:{id:'song-a',title:'Song A'},playing:false,speed:1,charColor:true,lines:[{t:1,end:3,text:'相同歌詞',chars:[]}]};
const view={hidden:false};
const context=vm.createContext({S:state,$:()=>view,performance:{now:()=>now},cur:()=>1,
  store:{get:(key,fallback)=>fallback},
  fetch:async (path,opts)=>{assert.equal(path,'/api/overlay');sent.push(JSON.parse(opts.body));return {ok:true};}});
vm.runInContext(source.slice(source.indexOf('const FURI ='),source.indexOf('function furiHTML(')),context);
vm.runInContext(part,context);
async function sync(){context.overlaySync();await new Promise(resolve=>setImmediate(resolve));now+=3000;}
(async()=>{
  await sync(); assert.equal(sent[0].lines[0].text,'相同歌詞');
  state.song={id:'song-b',title:'Song B'};
  await sync(); assert.equal(sent[1].sid,'song-b');assert.ok(sent[1].lines,'song change must resend lyrics');assert.equal(sent[1].lines[0].text,'相同歌詞');
  view.hidden=true;
  await sync();assert.equal(sent[2].sid,null);assert.equal(sent[2].playing,false);
  view.hidden=false;
  await sync();assert.equal(sent[3].lines[0].text,'相同歌詞');
  state.furiOn=true;state.kanaMode='hira';state.kanaFix={'相同':'そうどう'};
  vm.runInContext('FURI.map.set("相同歌詞", [{p:[["相同","そうとう"],["歌詞","かし"]]}])',context);
  now+=5000;await sync();assert.equal(sent[4].lines[0].r[0][1],'そうどう');
  state.kanaMode='romaji';now+=5000;await sync();assert.equal(sent[5].lines[0].r[0][1],'soudoukashi');
  console.log('Overlay song switching and return-to-library smoke passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
