const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../.github/workflows/tests.yml'), 'utf8').replace(/\r\n/g, '\n');
const testJob = source.split('  test:\n')[1]?.split('\n  coverage:\n')[0];
const revision = '${{ github.event.pull_request.head.sha || github.sha }}';
test('coverage requires no external upload or OIDC permission', () => {
  assert.doesNotMatch(source, /codecov|id-token:|use_oidc:|coverage_name:|\bgpg\b/i);
});
test('coverage artifact is exact revision and current run attempt bound', () => {
  const name = 'coverage-${{ github.run_id }}-${{ github.run_attempt }}-${{ github.event.pull_request.head.sha || github.sha }}';
  assert.ok(testJob?.includes(`name: ${name}`));
  assert.match(testJob, /uses: actions\/upload-artifact@v4\n        if: \$\{\{ env.ACT != 'true' \}\}/);
  assert.match(testJob, /path: coverage.xml\n          if-no-files-found: error\n          retention-days: 1/);
  assert.ok(testJob.includes(`ref: ${revision}`));
  assert.match(testJob, /persist-credentials: false/);
  assert.doesNotMatch(testJob, /continue-on-error|always\(\)/);
});
test('both test paths retain application coverage measurement', () => {
  assert.match(testJob, /run: uv run pytest tests\/ -v --cov=app --cov-report=xml/);
  assert.match(testJob, /run: python -m pytest tests\/ -v --cov=app --cov-report=xml/);
});
test('workflow discovers coverage regressions in its actual Node test command', () => {
  assert.match(testJob, /run: node --test tests\/ci-metadata.test.cjs tests\/ci-coverage.test.cjs/);
});
