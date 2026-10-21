// Exercise mode/provider switches and saves against the shipped HTML IDs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('static/index.html','utf8');
const js = fs.readFileSync('static/app.js','utf8');
const elements = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m => [m[1], {
  value:'',checked:false,hidden:true,disabled:false,addEventListener(){},scrollIntoView(){},
}]));
const cfg = {ai_mode:'local',api_provider:'openai',ai_setup_complete:false,ollama_auto_model:true,
  ollama_url:'http://127.0.0.1:11434',ollama_model:'qwen2.5:3b',openai_model:'gpt-4.1-mini',
  claude_model:'claude-sonnet-4-6',gemini_model:'gemini-2.5-flash',has_keys:{openai:true,claude:false,gemini:false},
  whisper_model:'large-v3-turbo',lyrics_language:'zh',convert_to_taiwan:true,
  separation_model:'UVR-MDX-NET-Inst_HQ_3.onnx',karaoke_model:'UVR_MDXNET_KARA_2.onnx',pitch_model:'auto'};
let saved, appliedFont, prepared=0;
const context = vm.createContext({
  $: selector => {const element=elements[selector.slice(1)];assert.ok(element,selector);return element;},
  api: async (path,opts) => {
    if(path==='/api/config' && opts) {saved=opts.json;Object.assign(cfg,saved);return {...cfg};}
    if(path==='/api/config') return {...cfg};
    if(path==='/api/status') return {modules:{},ai_provider:cfg.api_provider};
    if(path==='/api/ai/hardware') return {model:'qwen2.5:14b',num_ctx:16384,reason:'RTX 24 GB'};
    if(path==='/api/ai/prepare') {assert.equal(cfg.ai_mode,'local');prepared++;return {job:'setup',model:cfg.ollama_model};}
    throw new Error(path);
  },applyFont(font){appliedFont=font;},renderUsage:async()=>{},pollJobs(){},toast(){},waitJob:async(id,step)=>{step({step:'done',progress:1});},
});
const start=js.indexOf('let settingsKeys =');
const end=js.indexOf('/* ------------------------------------------------------------ 啟動 */',start);
vm.runInContext(js.slice(start,end),context);
(async()=>{
  await context.openSettings();
  assert.equal(elements['cfg-local'].hidden,false);
  assert.equal(elements['cfg-api'].hidden,true);
  assert.equal(elements['cfg-local-model'].value,'qwen2.5:14b');
  assert.equal(elements['cfg-local-model'].disabled,true);
  for(const provider of ['claude','gemini','openai']) {
    elements['cfg-ai-mode'].value='api';elements['cfg-provider'].value=provider;context.updateAIMode();
    assert.equal(elements['cfg-local'].hidden,true);
    assert.equal(elements['cfg-api'].hidden,false);
    for(const other of ['openai','claude','gemini']) assert.equal(elements['cfg-'+other].hidden,other!==provider);
    elements['cfg-'+provider+'-key'].value='private-'+provider;
    elements['cfg-font'].value='sans';
    await context.saveSettings();
    assert.equal(saved.font,'sans');assert.equal(appliedFont,'sans');
    assert.equal(saved.api_provider,provider);assert.equal(saved.ai_mode,'api');
    assert.equal(saved[provider==='claude'?'anthropic_api_key':provider+'_api_key'],'private-'+provider);
    assert.equal(elements['cfg-'+provider+'-key'].value,'');
    assert.equal(prepared,0,'API mode must not prepare Ollama');
  }
  elements['cfg-ai-mode'].value='local';elements['cfg-auto-model'].checked=false;context.updateAIMode();
  elements['cfg-local-model'].value='custom:7b';
  await context.saveSettings();assert.equal(saved.ollama_model,'custom:7b');assert.equal(prepared,1);
  elements['cfg-auto-model'].checked=true;context.updateAIMode();
  await context.saveSettings();assert.equal(saved.ollama_model,'qwen2.5:14b');assert.equal(prepared,2);
  assert.equal(elements['cfg-save'].disabled,false);
  assert.equal(elements['settings'].hidden,true);
  console.log('AI mode, all provider cards, private key saves, auto/custom model and download flow passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
