import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import test from 'node:test';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { validateMdx, missingLocalLinks } from '../scripts/validate_mdx.mjs';

test('generated Markdown preserves literal JSON and placeholders outside code', async () => {
  const markdown = '# Example\n\nLiteral {token}. Inline `{token}`.\n\n```json\n{"pitch": 60}\n```\n{"pitch": 61}\n\n~~~json\n{"pitch": 62}\n~~~\n';
  const withMath = markdown + '\n$$\n\\frac{a}{b}\n$$\n';
  const generated = execFileSync('python3', ['-c',
    'import sys;from scripts.sync_from_platformbackend import convert_markdown_to_mdx;print(convert_markdown_to_mdx(sys.stdin.read(),"Example"))'
  ], { input: withMath, encoding: 'utf8' });
  assert.ok(generated.includes('Literal &#123;token&#125;'));
  assert.ok(generated.includes('\\frac{a}{b}'));
  assert.ok(generated.includes('`{token}`'));
  assert.ok(generated.includes('```json\n{"pitch": 60}\n```'));
  await validateMdx(generated);
});

test('syntax gate rejects malformed MDX without executing it', async () => {
  await assert.rejects(validateMdx('# Broken\n\n{"pitch": 60}'));
  await assert.rejects(validateMdx('<Card>unclosed'));
});

test('Mintlify math remains valid alongside MDX expressions', async () => {
  await validateMdx('$$\n\\text{USD} = \\frac{price}{amount}\n$$');
});

test('link gate checks Markdown and card targets while preserving external URLs', async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'docs-links-'));
  try {
    await mkdir(path.join(root, 'en'));
    await writeFile(path.join(root, 'en/target.mdx'), '# Target');
    const links = await validateMdx('[Relative](target)\n\n<Card href="/en/target">Target</Card>\n\n[External](https://example.org) [Missing](/en/absent)');
    assert.deepEqual(await missingLocalLinks(root, path.join(root, 'en/index.mdx'), links), ['/en/absent']);
  } finally { await rm(root, { recursive: true }); }
});
