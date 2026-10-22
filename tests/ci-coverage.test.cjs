const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../.github/workflows/tests.yml'), 'utf8').replace(/\r\n/g, '\n');
const testJob = source.split('  test:\n')[1]?.split('\n  coverage:\n')[0];
const uploadJob = source.split('\n  coverage:\n')[1];
const revision = '${{ github.event.pull_request.head.sha || github.sha }}';
test('OIDC is isolated from all project execution', () => {
  assert.ok(uploadJob, 'separate authenticated upload job required');
  assert.doesNotMatch(testJob, /id-token:|codecov-action/);
  assert.match(uploadJob, /permissions:\n      contents: read\n      id-token: write/);
  assert.doesNotMatch(source.split('jobs:')[0], /id-token:/);
  assert.doesNotMatch(uploadJob, /pytest|uv sync|pip install|node --test|setup-python|setup-node/);
  assert.match(uploadJob, /sparse-checkout: \.github\/CODEOWNERS\n          sparse-checkout-cone-mode: false/);
});
test('upload inherits the tested owner and event trust boundary', () => {
  assert.ok(uploadJob);
  const guard = job => job.match(/^    if: (.+)$/m)?.[1];
  assert.equal(guard(uploadJob), guard(testJob));
  assert.match(uploadJob, /needs: test/);
  assert.doesNotMatch(uploadJob, /always\(\)|continue-on-error/);
});
test('coverage artifact is exact revision and current run attempt bound', () => {
  const name = 'coverage-${{ github.run_id }}-${{ github.run_attempt }}-${{ github.event.pull_request.head.sha || github.sha }}';
  assert.ok(testJob?.includes(`name: ${name}`));
  assert.match(testJob, /coverage_name: \$\{\{ format\('coverage-\{0\}-\{1\}-\{2\}', github.run_id, github.run_attempt, github.event.pull_request.head.sha \|\| github.sha\) \}\}/);
  assert.match(uploadJob, /name: \$\{\{ needs.test.outputs.coverage_name \}\}/);
  assert.match(uploadJob, /uses: actions\/download-artifact@v4\n        if: \$\{\{ env.ACT != 'true' \}\}/);
  assert.match(testJob, /uses: actions\/upload-artifact@v4/);
  assert.match(testJob, /path: coverage.xml\n          if-no-files-found: error/);
  assert.match(uploadJob, /uses: actions\/download-artifact@v4/);
  assert.doesNotMatch(uploadJob, /run-id:|github-token:|merge-multiple:|pattern:/);
  assert.ok(uploadJob.includes(`ref: ${revision}`));
  assert.ok(uploadJob.includes(`override_commit: ${revision}`));
  assert.match(uploadJob, /persist-credentials: false/);
});
test('pinned authenticated upload fails visibly and retains integrity verification', () => {
  assert.ok(uploadJob);
  assert.match(uploadJob, /codecov\/codecov-action@0fb7174895f61a3b6b78fc075e0cd60383518dac/);
  for (const input of ['use_oidc: true', 'fail_ci_if_error: true', 'disable_search: true', 'plugins: noop', 'disable_file_fixes: true']) assert.ok(uploadJob.includes(input), input);
  assert.doesNotMatch(source, /secrets\.|CODECOV_TOKEN|skip_validation:|use_pypi:|binary:|dry_run:|handle_no_reports_found:/);
  assert.match(uploadJob, /files: \.\/coverage.xml/);
});
test('workflow discovers coverage regressions in its actual Node test command', () => {
  assert.match(testJob, /run: node --test tests\/ci-metadata.test.cjs tests\/ci-coverage.test.cjs/);
});
