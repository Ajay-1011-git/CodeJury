"""Checks the Stage 2 instruction pack and synthetic fixtures, never candidate execution.

Requires jsonschema with Draft 2020-12 support. Run from any directory.
"""
from pathlib import Path
from jsonschema import Draft202012Validator
import ast,copy,hashlib,json,re

ROOT=Path(__file__).resolve().parents[1]
def digest(b):return hashlib.sha256(b).hexdigest()
def load(name):return json.loads((ROOT/name).read_text())
schema=load('contracts/stage2.schema.json')
Draft202012Validator.check_schema(schema)
sha=digest((ROOT/'contracts/stage2.schema.json').read_bytes())
assert sha==(ROOT/'contracts/SHA256SUMS').read_text().split()[0]
assert digest((ROOT/'reference/stage1-v1-api.schema.json').read_bytes())=='5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df'
def val(name):return Draft202012Validator({**schema,'$ref':'#/$defs/'+name})
shared=(ROOT/'CodeJury-Stage2-Shared-Contract.md').read_text().rstrip()
ports=(ROOT/'contracts/shared/stage2_ports.py').read_text().rstrip()
ast.parse(ports)
counts={}
for owner,prefix in [('Ajay','A2.'),('Sarvesh','S2.')]:
 text=(ROOT/f'CodeJury-Stage2-{owner}.md').read_text()
 assert shared in text and ports in text and sha in text
 assert json.loads(re.search(r'```json\n(.*?)\n```',text,re.S).group(1))==schema
 tasks=re.findall(r'^## ([AS]2\.\d+) · .*? · depends: ([^\n]+)',text,re.M)
 seen=set()
 for tid,deps in tasks:
  assert tid.startswith(prefix) and tid not in seen
  for d in deps.split(', '):
   if d!='none':assert d in seen,(tid,d)
  seen.add(tid)
 assert len(tasks)==12 and text.count('**VERIFY**')==12
 counts[owner]=len(tasks)
 assert 'quality upgrade was not implemented' in text or 'quality upgrade not implemented' in text
for p in ROOT.rglob('*.md'):
 assert len(re.findall(r'^```',p.read_text(),re.M))%2==0,p
manifest=load('contracts/fixtures/fixture-manifest.json');assert manifest['synthetic'] is True
files={}
for item in manifest['fixtures']:
 name=item['filename'];assert name not in files
 data=load('contracts/fixtures/'+name);val(item['definition']).validate(data);files[name]=data
 if 'runtime_mode' in data:assert data['runtime_mode']=='fixture'

def source_check(c):
 assert c['source_hash']==digest(c['source'].encode())
 ast.parse(c['source']) # parsing only, never import/compile/evaluate on host
def pool_check(cs,tests,executions):
 byid={c['candidate_id']:c for c in cs};assert len(byid)==len(cs)
 tids={t['test_id']:t for t in tests};assert len(tids)==len(tests)
 signatures=set()
 for c in cs:
  source_check(c)
  sig=ast.dump(ast.parse(c['source']),include_attributes=False);assert sig not in signatures;signatures.add(sig)
  if c['parent_id'] is not None:assert c['parent_id'] in byid
  visited=set();cursor=c
  while cursor['parent_id'] is not None:
   assert cursor['candidate_id'] not in visited;visited.add(cursor['candidate_id']);cursor=byid[cursor['parent_id']]
  if c['origin']=='ast_search':
   expected=byid[c['parent_id']]['source_hash']
   for edit in c['edits']:
    assert edit['parent_source_hash']==expected;expected=edit['result_source_hash']
   assert expected==c['source_hash']
 hard={t['test_id'] for t in tests if t['oracle_status']=='authoritative'}
 ids=set()
 for e in executions:
  assert e['execution_id'] not in ids;ids.add(e['execution_id'])
  assert e['candidate_id'] in byid and e['test_id'] in tids
  if tids[e['test_id']]['oracle_status']!='authoritative':assert e['outcome'] not in ('pass','fail')
 for c in cs:
  if c['eligibility']=='eligible':
   passed={e['test_id'] for e in executions if e['candidate_id']==c['candidate_id'] and e['outcome']=='pass'}
   assert hard<=passed and c['verification_suite_hash'] is not None
 return byid

for item in manifest['fixtures']:
 data=files[item['filename']];definition=item['definition']
 if definition in ('Candidate','CandidateDraft','Problem','ProbeMutant','SourceArtifact'):source_check(data)
 if definition=='TestProposal' or definition=='CriticDraft':assert (data['generator_spec'] is None)!=(data['concrete_inputs'] is None)
 if definition=='RunSnapshot':
  cs=pool_check(data['candidates'],data['tests'],data['executions'])
  for m in data['probe_mutants']:source_check(m);assert m['parent_candidate_id'] in cs
  for s in data['edit_sources']:source_check(s)
  if data['status']=='supported_patch':
   selected=cs[data['decision']['selected_candidate_id']]
   assert selected['eligibility']=='eligible' and selected['origin']!='original'
   assert data['suite_hash']==data['decision']['suite_hash']==selected['verification_suite_hash']
  elif data['status'] not in ('queued','running'):assert data['decision']['selected_candidate_id'] is None
 if definition=='EpisodeBundle':
  cs=pool_check(data['candidates'],data['tests'],data['executions'])
  assert data['state']['problem_id']==data['problem']['problem_id']
  assert {c['candidate_id'] for c in data['state']['candidate_summaries']}==set(cs)
  opts={o['option_id'] for o in data['state']['available_actions']};assert len(opts)==len(data['state']['available_actions'])
 if definition=='BenchmarkReport':
  assert len({r['method'] for r in data['rows']})==len(data['rows'])
  for row in data['rows']:
   assert row['total_base_problems']==sum(row[k] for k in ['solved','incorrect_accepted','unresolved','invalid_input','infrastructure_error','cancelled'])
  if data['status']=='not_run':assert not data['rows'] and data['dataset_id'] is None
 if definition=='TrainingReport':
  assert len({r['role'] for r in data['cards']})==len(data['cards'])
  for card in data['cards']:
   if card['status']=='completed':assert card['adapter_hash'] and card['steps']>0
 if definition in ('MethodResult','RolloutResult'):
  if data['selected_source'] is not None:assert digest(data['selected_source'].encode())==data['selected_source_hash']
  pool=data.get('candidate_pool',data.get('episode',{}).get('candidates',[]))
  sid=data['final_result']['selected_candidate_id']
  if sid:assert any(c['candidate_id']==sid and c['source_hash']==data['selected_source_hash'] for c in pool)

handshakes=[]
for op in ['validate','evaluate','search','audit','investigate']:
 request=files[f'tool-{op}-request.json'];response=files[f'tool-{op}-result.json']
 assert request['request_id']==response['request_id'] and request['parameters']['operation']==op
 prefix=request['id_prefix']
 for field,key in [('candidates','candidate_id'),('tests','test_id'),('executions','execution_id'),('mutants','mutant_id'),('audit_gaps','gap_id')]:
  for row in response[field]:assert row[key].startswith(prefix+'-')
 if op=='validate':assert response['validation']['valid'] and not response['executions']
 if op=='evaluate':assert not response['candidates'] and not response['tests']
 if op=='search':
  for c in response['candidates']:source_check(c)
  assert not response['mutants'] and not response['audit_gaps']
 if op=='audit':assert not response['candidates'] and response['mutants'] and response['audit_gaps']
 if op=='investigate':assert response['tests'] and not response['candidates']
 handshakes.append(op)
assert files['model-request.json']['request_id']==files['model-response.json']['request_id']
assert files['model-request.json']['role']==files['model-response.json']['role']
val('RepairDraft').validate(json.loads(files['model-response.json']['text']))
jd=files['judge-draft.json'];state=files['state-snapshot.json']
assert jd['state_id']==state['state_id'] and jd['action_option_id'] in {o['option_id'] for o in state['available_actions']}
assert files['method-request.json']['method']==files['method-result.json']['method']
assert files['method-request.json']['request_id']==files['method-result.json']['request_id']
assert files['method-request.json']['config_hash']==files['method-result.json']['config_hash']

negative=[]
def reject(definition,label,base,change):
 x=copy.deepcopy(base);change(x);assert list(val(definition).iter_errors(x)),label;negative.append(label)
request=files['run-create.json'];candidate=files['candidate-search.json']
for label,change in [('old Stage1 version',lambda x:x.update(schema_version='stage1.v1')),('unimplemented upgrade version',lambda x:x.update(schema_version='stage1.v1.1')),
 ('unknown wire field',lambda x:x.update(extra=1)),('missing domain',lambda x:x.pop('domain_schema')),('wrong profile',lambda x:x.update(resource_profile='stage1-demo')),
 ('unsupported float output expectation',lambda x:x['supplied_tests'][0].update(expected=1.25))]:reject('RunCreate',label,request,change)
for label,change in [('search mislabelled B',lambda x:x.update(origin='fixer_b')),('search missing edits',lambda x:x.update(edits=[])),('search parent null',lambda x:x.update(parent_id=None)),
 ('unsupported edit operator',lambda x:x['edits'][0].update(operator_family='hardcode_test')),('missing source hash',lambda x:x.pop('source_hash'))]:reject('Candidate',label,candidate,change)
reject('InvestigationAction','action/parameter tag mismatch',files['state-snapshot.json']['available_actions'][0]['action'],lambda x:x.update(kind='select'))
reject('ToolRequest','unknown operation',files['tool-search-request.json'],lambda x:x['parameters'].update(operation='execute_on_host'))
reject('ToolRequest','search cap exceeded',files['tool-search-request.json'],lambda x:x['parameters'].update(candidate_limit=49))
reject('ToolRequest','budget exceeds profile',files['tool-search-request.json'],lambda x:x['remaining_budget'].update(output_tokens=10001))
reject('ModelRequest','unknown model role',files['model-request.json'],lambda x:x.update(role='judge_oracle'))
reject('ModelResponse','missing actual usage',files['model-response.json'],lambda x:x.pop('usage'))
reject('JudgeDraft','Judge proposes code',jd,lambda x:x.update(source='return hidden_answer'))
reject('RunSnapshot','missing probe provenance',files['snapshot-supported.json'],lambda x:x.pop('probe_mutants'))
reject('ArtifactManifest','unknown split',files['artifact-manifest.json'],lambda x:x.update(split='all_unchecked'))
print(json.dumps({'status':'passed','schema_sha256':sha,'schema_definitions':len(schema['$defs']),'fixtures':len(files),'tasks':counts,'tool_handshakes':handshakes,
 'negative_structural_cases':negative,'scope':'Documents and synthetic fixtures only. No Mac training/inference, candidate execution or real benchmark.'},indent=2))
