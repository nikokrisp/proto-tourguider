const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function application(protocol='http:') {
  const main = {innerHTML:'', focus(){}, setAttribute(){},removeAttribute(){},querySelector(){return {addEventListener(){}};}};
  const live = {textContent:''};
  const context = vm.createContext({document:{querySelector:s=>s==='#main'?main:live, addEventListener(){}},window:{scrollTo(){},location:{protocol,href:''}},Intl,AbortController,setTimeout,clearTimeout,TypeError,console});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../frontend/assets/app.js'),'utf8'),context);
  return {context,main};
}

test('opening index.html directly shows server instructions',()=>{
  const {context,main}=application('file:');
  assert.equal(vm.runInContext('state.screen',context),'local-file');
  assert.match(main.innerHTML,/run\.command/);
  assert.match(main.innerHTML,/http:\/\/127\.0\.0\.1:8765\//);
  assert.doesNotMatch(main.innerHTML,/question-card/);
});

for (const original of [['1'],[]]) {
  test(`failed edit stays visible; retry preserves ${original.length?'chosen answer':'unknown answer'}`, async()=>{
    const {context,main}=application();
    context.initial=original;
    vm.runInContext(`state.screen='consultation'; state.consultation={complete:false,answers:{form_a:initial},summary:[{field:'form_a'}],question:{field:'form_f'}}; fetch=async()=>{throw new TypeError('offline')};`,context);
    await vm.runInContext(`edit('form_a')`,context);
    assert.equal(vm.runInContext('state.screen',context),'error');
    assert.match(main.innerHTML,/error-box/);
    assert.doesNotMatch(main.innerHTML,/question-card/);
    assert.equal(vm.runInContext('state.pendingEdit.field',context),'form_a');
    vm.runInContext(`fetch=async()=>({ok:true,json:async()=>({complete:false,answers:{},summary:[],question_number:1,question:{field:'form_a',label:'Usia',title:'Usia?',hint:'Pilih',multiple:true,options:[{value:'1',label:'20–39'}]}})})`,context);
    const success=await vm.runInContext('sendAnswers(state.retryAnswers)',context);
    assert.equal(success,true);
    assert.equal(vm.runInContext('state.screen',context),'consultation');
    assert.equal(vm.runInContext('JSON.stringify(state.selected)',context),JSON.stringify(original));
    assert.equal(vm.runInContext('state.unknown',context),!original.length);
    assert.equal(vm.runInContext('state.pendingEdit',context),null);
  });
}
