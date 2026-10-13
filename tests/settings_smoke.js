// Exercise the actual settings handlers against the IDs in the shipped HTML.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('static/index.html', 'utf8');
const js = fs.readFileSync('static/app.js', 'utf8');
const local = html.includes('id="cfg-url"');
const elements = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m => [m[1], {
  value: '', checked: false, hidden: true, addEventListener() {}, scrollIntoView() {},
}]));
const cfg = {ollama_url: 'http://127.0.0.1:11434', ollama_model: 'qwen2.5:14b',
  openai_model: 'gpt-4.1-mini', has_key: true, openai_api_key: 'sk-mask…1234',
  balance_usd: null, ai_input_price: null, ai_output_price: null,
  whisper_model: 'large-v3-turbo', lyrics_language: 'zh', convert_to_taiwan: true,
  separation_model: 'UVR-MDX-NET-Inst_HQ_3.onnx', karaoke_model: 'UVR_MDXNET_KARA_2.onnx', pitch_model: 'auto'};
let saved;
const context = vm.createContext({
  $: selector => { const element=elements[selector.slice(1)]; assert.ok(element,selector); return element; },
  api: async (path, options) => {
    if (path==='/api/config' && options) { saved=options.json; return {}; }
    if (path==='/api/config') return cfg;
    if (path==='/api/status') return {modules:{}};
    throw new Error(path);
  }, renderUsage: async () => {}, pollJobs() {}, toast() {},
});
const start=js.indexOf('async function openSettings(');
const end=js.indexOf('/* ------------------------------------------------------------ 啟動 */',start);
vm.runInContext(js.slice(start,end),context);
(async () => {
  await context.openSettings();
  assert.equal(elements['settings'].hidden,false);
  const key=local?'ollama_model':'openai_model';
  assert.equal(elements['cfg-model'].value,cfg[key]);
  if (local) {
    elements['cfg-url'].value='http://127.0.0.1:12345';
  } else {
    assert.equal(elements['cfg-key'].value,'');
    elements['cfg-key'].value='sk-test-only';
    elements['cfg-input-price'].value='0.4';
    elements['cfg-output-price'].value='1.6';
    elements['cfg-model'].value='another-model';
    elements['cfg-model'].oninput();
    assert.equal(elements['cfg-input-price'].value,'');
    assert.equal(elements['cfg-output-price'].value,'');
  }
  await context.saveSettings();
  assert.ok(saved);
  assert.equal(saved[key],elements['cfg-model'].value);
  assert.equal(elements['settings'].hidden,true);
  if (local) {
    assert.equal(saved.ollama_url,'http://127.0.0.1:12345');
    assert.ok(!('openai_api_key' in saved));
  } else {
    assert.equal(saved.openai_api_key,'sk-test-only');
    assert.equal(saved.ai_price_model,'another-model');
    assert.equal(saved.ai_input_price,'');
  }
  console.log(`${local?'Ollama':'OpenAI'} settings load/save smoke passed`);
})().catch(error => { console.error(error); process.exitCode=1; });
