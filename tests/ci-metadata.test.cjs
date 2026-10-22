const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const yaml = fs.readFileSync(path.join(__dirname, '../.github/workflows/pr-checks.yml'), 'utf8').replace(/\r\n/g, '\n');
const scripts = [...yaml.matchAll(/          script: \|\n((?:            .*\n|\n)+)/g)].map(m => m[1].split('\n').map(l => l.slice(12)).join('\n'));
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
const sha = 'a'.repeat(40), base = 'b'.repeat(40);
function pr() { return {number: 7, state: 'open', user: {login: 'daddyparodz'}, labels: [{name: 'bug'}], assignees: [{login: 'existing'}], base: {sha: base, ref: 'main', repo: {id: 1, full_name: 'daddyparodz/gmail-cleaner'}}, head: {sha, repo: {id: 1, full_name: 'daddyparodz/gmail-cleaner'}}}; }
async function run(index, mutate = () => {}, actor = '45983094', configure = () => {}) {
  let reads = 0, writes = 0, failures = 0;
  const context = {eventName: 'workflow_dispatch', actor: 'daddyparodz', sha: base, ref: 'refs/heads/main', repo: {owner: 'daddyparodz', repo: 'gmail-cleaner'}, payload: {repository: {id: 1, full_name: 'daddyparodz/gmail-cleaner', owner: {id: 45983094}}, inputs: {pr_number: '7', head_sha: sha}}};
  const github = {rest: {pulls: {get: async () => { const data = pr(); mutate(data, ++reads, context); return {data}; }}, issues: {addAssignees: async args => { assert.deepEqual(args.assignees, ['daddyparodz']); writes++; }}}};
  const core = {setFailed: () => failures++, warning: () => {}, summary: {addHeading(){return this;}, addRaw(){return this;}, async write(){}}};
  const process = {env: {GITHUB_ACTOR_ID: actor, GITHUB_TRIGGERING_ACTOR: 'daddyparodz'}};
  configure(context, process);
  try { await new AsyncFunction('github','context','core','process', scripts[index])(github,context,core,process); return {reads,writes,failures}; }
  catch (error) { return {reads,writes,failures,error}; }
}
test('metadata workflows have two executable inline checks and no checkout', () => { assert.equal(scripts.length, 2); assert.ok(!yaml.includes('actions/checkout')); assert.ok(!yaml.includes('pull_request:')); });
for (const index of [0,1]) {
  test(`job ${index} validates fresh provenance before checks`, async () => { const r = await run(index); assert.ifError(r.error); assert.equal(r.reads, 2); assert.equal(r.writes, index); });
  test(`job ${index} rejects unauthorized actor before HTTP`, async () => { const r = await run(index, undefined, '9'); assert.ok(r.error); assert.equal(r.reads, 0); assert.equal(r.writes, 0); });
  for (const [name, mutation] of Object.entries({wrongrepo: p => p.base.repo.full_name = 'evil/repo', fork: p => p.head.repo.id = 2, number: p => p.number = 8, newhead: (p,n) => {if(n===2)p.head.sha='c'.repeat(40);}, staleBase: p => p.base.sha = 'd'.repeat(40)})) {
    test(`job ${index} rejects ${name} without mutation`, async () => { const r = await run(index, mutation); assert.ok(r.error); assert.equal(r.writes, 0); });
  }
}
for (const index of [0, 1]) {
  for (const value of ['', '0', '-1', '1.5', '1;echo evil', '9007199254740992']) {
    test(`job ${index} rejects malformed PR ${JSON.stringify(value)} before HTTP`, async () => {
      const r = await run(index, undefined, undefined, c => c.payload.inputs.pr_number = value);
      assert.ok(r.error); assert.equal(r.reads, 0); assert.equal(r.writes, 0);
    });
  }
  for (const [name, configure] of Object.entries({
    wrongEvent: c => c.eventName = 'pull_request_target',
    wrongRef: c => c.ref = 'refs/heads/evil',
    wrongOwner: c => c.payload.repository.owner.id = 9,
    wrongRerunner: (c, p) => p.env.GITHUB_TRIGGERING_ACTOR = 'outsider',
    badSha: c => c.payload.inputs.head_sha = 'main',
  })) {
    test(`job ${index} rejects ${name} before HTTP`, async () => {
      const r = await run(index, undefined, undefined, configure);
      assert.ok(r.error); assert.equal(r.reads, 0); assert.equal(r.writes, 0);
    });
  }
  test(`job ${index} rejects wrong base branch`, async () => {
    const r = await run(index, p => p.base.ref = 'other');
    assert.ok(r.error); assert.equal(r.writes, 0);
  });
}
const testsYaml = fs.readFileSync(path.join(__dirname, '../.github/workflows/tests.yml'), 'utf8');
test('CI executes metadata regression suite', () => {
  assert.match(testsYaml, /run: node --test tests\/ci-metadata\.test\.cjs/);
  assert.match(testsYaml, /actions\/setup-node@/);
});
test('owner-only job event guards reject untrusted event paths', () => {
  const sources = [testsYaml, yaml];
  for (const [i, source] of sources.entries()) {
    const guards = [...source.matchAll(/^    if: (.+)$/gm)].map(m => m[1].trim());
    assert.equal(guards.length, i === 0 ? 1 : 2);
    for (const guard of guards) {
      const allows = github => new Function('github', 'startsWith', `return (${guard});`)(github, (s, p) => s.startsWith(p));
      const owner = {repository_owner_id: '45983094', actor_id: '45983094', triggering_actor: 'daddyparodz', event_name: 'workflow_dispatch', ref: 'refs/heads/main'};
      assert.equal(allows(owner), true);
      for (const change of [{actor_id: '9'}, {repository_owner_id: '9'}, {triggering_actor: 'outsider'}, {event_name: 'pull_request'}, {event_name: 'pull_request_target'}, {event_name: 'workflow_run'}, {event_name: 'issue_comment'}, {ref: 'refs/tags/v1'}]) {
        assert.equal(allows({...owner, ...change}), false, JSON.stringify(change));
      }
      assert.equal(allows({...owner, event_name: 'push'}), i === 0);
      assert.equal(allows({...owner, ref: 'refs/heads/topic'}), i === 0);
    }
  }
});
test('missing labels still fail', async () => { const r = await run(0, p => p.labels = []); assert.ifError(r.error); assert.equal(r.failures, 1); });
test('existing creator assignment is preserved without write', async () => { const r = await run(1, p => p.assignees.push({login:'daddyparodz'})); assert.ifError(r.error); assert.equal(r.writes,0); });
