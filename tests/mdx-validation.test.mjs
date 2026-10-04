import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import test from 'node:test';
import { validateMdx } from '../scripts/validate_mdx.mjs';

test('generated Markdown preserves literal JSON and placeholders outside code', async () => {
  const markdown = '# Example\n\nLiteral {token}. Inline `{token}`.\n\n```json\n{"pitch": 60}\n```\n{"pitch": 61}\n\n~~~json\n{"pitch": 62}\n~~~\n';
  const generated = execFileSync('python3', ['-c',
    'import sys;from scripts.sync_from_platformbackend import convert_markdown_to_mdx;print(convert_markdown_to_mdx(sys.stdin.read(),"Example"))'
  ], { input: markdown, encoding: 'utf8' });
  assert.ok(generated.includes('Literal &#123;token&#125;'));
  assert.ok(generated.includes('`{token}`'));
  assert.ok(generated.includes('```json\n{"pitch": 60}\n```'));
  await validateMdx(generated);
});

test('syntax gate rejects malformed MDX without executing it', async () => {
  await assert.rejects(validateMdx('# Broken\n\n{"pitch": 60}'));
  await assert.rejects(validateMdx('<Card>unclosed'));
});
