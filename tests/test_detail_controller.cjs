const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({});
for (const name of ['detail-controller', 'explanation-editor']) {
  vm.runInContext(fs.readFileSync('ui/' + name + '.js', 'utf8'), context);
}
const tick = () => new Promise(resolve => setImmediate(resolve));
function dom() {
  const nodes = new Map();
  const query = selector => {
    if (!nodes.has(selector)) nodes.set(selector, {
      dataset: {}, value: '', open: false, scrollTop: 17,
      querySelectorAll: () => [], querySelector: () => null,
      addEventListener() {}, showModal() { this.open = true; },
      close() { this.open = false; }
    });
    return nodes.get(selector);
  };
  return query;
}
(async () => {
  const $ = dom();
  let flow = {revision: 1, actions: [], artifacts: {}, states: []};
  let resolve, reject;
  const messages = [], calls = [];
  let hash = '';
  const controller = context.SaigenDetailController.create({
    query: $, escape: String, getFlow: () => flow, getState: () => null,
    getEvents: () => [], getHash: () => hash, goBack: () => { hash = ''; },
    request: path => { calls.push(path); return new Promise((a,b) => { resolve=a; reject=b; }); },
    toast: message => messages.push(message)
  });
  controller.load('old'); controller.load('old');
  assert.equal(calls.length, 1, 'deduplicate in-flight reads');
  flow = {...flow, revision: 2};
  resolve({revision: 1, state: {id: 'old'}}); await tick();
  assert.equal(controller.state('old'), undefined, 'discard stale revision');
  controller.load('archived');
  resolve({revision: 2, state: {id: 'archived'}}); await tick();
  assert.equal(controller.state('archived').id, 'archived');
  hash = '#state/failure'; controller.load('failure');
  reject(new Error('Unavailable')); await tick();
  assert.equal(messages.at(-1), 'Unavailable');
  $('#failed-story-back').onclick(); assert.equal(hash, '');

  hash = '#state/late'; controller.load('late');
  flow = {...flow, revision: 3};
  const beforeMessages = messages.length; reject(new Error('Old failure')); await tick();
  assert.equal(messages.length, beforeMessages, 'ignore stale failed read');
  flow = {...flow, revision: 2};

  for (const name of ['SaigenStory', 'SaigenVerification', 'SaigenDetails']) {
    context[name] = {create: () => ({render: () => ''})};
  }
  const reviewDom = dom();
  const review = {dataset: {reconstruction:'p', decision:'accept', stateId:'a'}};
  const approval = {dataset: {verifyApprove:'v', digest:'hash'}};
  reviewDom('#detail-content').querySelectorAll = selector =>
    selector === '[data-reconstruction]' ? [review] : selector === '[data-verify-approve]' ? [approval] : [];
  reviewDom('[data-review-reason="p"]').value = 'Checked selected evidence';
  const mutations = [];
  let conflict = true;
  const actions = context.SaigenDetailController.create({
    query:reviewDom, escape:String, getFlow:()=>flow, getHash:()=>'', getState:()=>null,
    request:async (path, body) => {
      if (!body) return {revision:flow.revision, state:{id:'a'}};
      mutations.push({path,body}); if(conflict) throw new Error('Conflict'); return flow;
    },
    accept:async()=>{}, toast:()=>{}, firstPlot:()=>null, firstTable:()=>null,
    terminalMarkup:()=>'', bindOriginalCommands:()=>{}, editor:{},
  });
  actions.render({id:'a', title:'Result', status:'completed'});
  await review.onclick();
  assert.equal(review.disabled, false, 'failed review can be retried');
  assert.equal(mutations[0].body.stateId, 'a');
  assert.equal(mutations[0].body.reason, 'Checked selected evidence');
  conflict = false; await approval.onclick();
  assert.equal(mutations[1].path, '/api/verifications/v/approve');
  assert.equal(mutations[1].body.digest, 'hash');
  assert.ok(mutations.every(call => !call.path.includes('execute')));

  const form = dom();
  const sent = [];
  let fail = true;
  const values = {kind: 'decision', summary: 'Keep weak signals', evidenceKind: 'reported',
    rationale: 'Exploratory analysis', agreementBasis: 'Requested', source: 'artifact:chat', location: 'line 3'};
  class Data {
    get(key) { return values[key] || ''; }
    getAll(key) { return {participantName: ['Researcher'], participantRole: ['contributor'], alternativeOption: ['Strict'], alternativeReason: ['Loses signals']}[key] || []; }
  }
  const editor = context.SaigenExplanationEditor.create({
    query: form, escape: String, field: () => '', getFlow: () => flow, FormData: Data,
    request: async (path, body) => { sent.push({path, body}); if(fail) throw new Error('Revision conflict'); return flow; },
    accept: async () => {}, toast: () => {}
  });
  const previous = {id: 'ex1', kind: 'decision', states: ['a', 'b'], actions: ['x', 'y'],
    evidence: [{type: 'event', id: 1, location: 'event'}]};
  editor.open({id:'a'}, {entries:[previous]}, true);
  flow = {...flow, revision: 3};
  const submit = {};
  const event = {preventDefault() {}, target: {querySelector: () => submit}};
  await form('#explanation-form').onsubmit(event);
  assert.equal(sent[0].body.revision, 2, 'submit against revision at form opening');
  assert.equal(form('#explanation-error').textContent, 'Revision conflict');
  assert.equal(submit.disabled, false); assert.equal(form('#explanation-dialog').open, true);
  fail = false; await form('#explanation-form').onsubmit(event);
  const entry = sent[1].body.entry;
  assert.equal(entry.supersedes, 'ex1');
  assert.equal(entry.actions.length, 2); assert.equal(entry.states.length, 2);
  assert.equal(entry.evidence.length, 2); assert.equal(entry.evidence[0].type, 'event');
  assert.equal(entry.rationale, values.rationale);
  assert.equal(form('#explanation-dialog').open, false);
  console.log('Detail loading and explanation interaction checks passed.');
})().catch(error => {console.error(error); process.exitCode = 1;});
