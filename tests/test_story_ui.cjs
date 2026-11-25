const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context=vm.createContext({});
vm.runInContext(fs.readFileSync('ui/story.js','utf8'),context);
const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ui=context.SaigenStory.create({escape,shortDate:v=>v||'Not recorded'});
const base={revision:1,state:{id:'result',title:'Result',status:'completed',note:'A general annotation'},entries:[],actions:[],participants:[],timeline:[],replacements:[]};
for(const status of ['planned','running','completed','failed','imported','cancelled','unknown','saved']){
 const html=ui.render({...base,state:{...base.state,status}},'<figure>Preview</figure>',{});
 assert.match(html,/aria-label="Results &amp; outputs"/);
 for(const label of ['History &amp; evidence','Scientific question','Findings','Interpretations','Limitations']){
   assert.ok(!html.includes(label));
 }
 assert.ok(!html.includes('not recorded'));
 assert.ok(html.includes('Current annotation'));
 assert.ok(!html.includes('>Future<'));
}
const decision={id:'ex1',kind:'decision',summary:'Choose DP ≥ 5 <script>',rationale:'Preserve weak signals',alternatives:[{option:'DP ≥ 10',reason:'Too strict for this comparison'}],agreementBasis:'Researcher requested exploration',recordedBy:'Agent',recordedAt:'2026-11-17',evidenceKind:'reported',participants:[],evidence:[{type:'artifact',id:'chat',location:'JSONL lines 42–45'}],historicalAt:'2020-01-01T10:00:00Z'};
let html=ui.render({...base,entries:[decision],participants:[{name:'Agent',role:'Recorder',context:'ex1'}],timeline:[{revision:2,kind:'explanation.recorded',at:'2026-11-17',actor:'Agent',payload:{summary:'<script>'}}]},'');
assert.match(html,/<h2>Background &amp; purpose<\/h2>/);
assert.match(html,/<details[^>]*story-history"><summary>History &amp; evidence<\/summary>.*Participants.*Timeline/);
assert.match(html,/<details class="story-evidence"><summary>Attribution &amp; evidence · 1<\/summary><p class="action-meta">reported statement · recorded by Agent/);
assert.ok(html.includes('Preserve weak signals'));
assert.ok(html.includes('DP ≥ 10'));
assert.ok(html.includes('Researcher requested exploration'));
assert.ok(html.includes('JSONL lines 42–45'));
assert.ok(html.includes('Reported historical date'));
assert.ok(html.includes('id="event-2"'));
assert.ok(!html.includes('<script>'));
assert.ok(html.includes('Recorder identity does not establish approval'));
assert.ok(!html.includes('Agreement participants'));
html=ui.render({...base,state:{...base.state,note:' '},entries:[{...decision,rationale:' ',alternatives:[],agreementBasis:'',evidence:[]}]},'');
assert.deepEqual([...html.matchAll(/<h2>([^<]+)<\/h2>/g)].map(match=>match[1]),['Background &amp; purpose']);
assert.doesNotMatch(html,/>Rationale<|>Alternatives considered<|>Basis for agreement<|Attribution &amp; evidence|Not recorded/i);
html=ui.render({...base,entries:[{...decision,kind:'finding',summary:'One recorded finding'}]},'',{});
assert.match(html,/<h3>Findings<\/h3>/);
assert.match(html,/Reported finding/);
assert.match(html,/One recorded finding/);
html=ui.render({...base,entries:[{...decision,supersededBy:'ex2'},{...decision,id:'ex2',summary:'Correction'}],archive:{label:'Cancelled proposal',reason:'Different method requested'},replacements:[{...decision,kind:'replacement',states:['old'],replacementStateId:'new'}]},'',{});
assert.ok(html.includes('Earlier statement (corrected)'));
assert.ok(html.includes('data-entry-link="ex2"'));
assert.ok(html.includes('Different method requested'));
assert.ok(html.includes('data-open="old"'));
assert.ok(html.includes('data-open="new"'));
html=ui.render({...base,actions:[{id:'a',label:'Filter',reason:'First purpose'},{id:'b',label:'Compare',reason:'Separate purpose'}]},'',{});
assert.ok(html.includes('First purpose'));
assert.ok(html.includes('Separate purpose'));
const expected={expectedSummary:'A table.',expectedFiles:['planned.csv']};
const details={inputs:'Input file',method:'Method explanation',outputs:'Actual file',history:'Execution log'};
html=ui.render({...base,state:{...base.state,...expected,status:'planned'},originalPlan:expected},'',{details:{...details,outputs:''},originalPlan:'Original plan'});
assert.deepEqual([...html.matchAll(/<h2>([^<]+)<\/h2>/g)].map(match=>match[1]),
 ['Background &amp; purpose','Expected outputs','Planned inputs','Proposed method &amp; code']);
assert.match(html,/planned\.csv/);
assert.doesNotMatch(html,/Actual file/);
html=ui.render({...base,state:{...base.state,...expected,note:'First purpose'},originalPlan:expected,actions:[{id:'a',reason:'First purpose'}]},'',{details,originalPlan:'Original plan',executionPlan:'Revised plan'});
assert.deepEqual([...html.matchAll(/<h2>([^<]+)<\/h2>/g)].map(match=>match[1]),
 ['Background &amp; purpose','Results &amp; outputs','Inputs','Method &amp; code']);
assert.equal(html.match(/First purpose/g).length,1);
assert.match(html,/<h2>Results &amp; outputs<\/h2>Actual file/);
assert.match(html,/Original recorded plan<\/summary>Original plan.*Plan at execution start<\/summary>Revised plan/);
assert.equal(ui.render({...base,state:{...base.state,note:''}},''),'');
console.log('Story UI: scientific context, planned and actual outputs, collapsed attribution and history, corrections, and escaping passed.');
