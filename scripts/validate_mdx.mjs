#!/usr/bin/env node
// Parse generated pages without evaluating any MDX/JSX or importing page code.
import { compile } from '@mdx-js/mdx';
import remarkGfm from 'remark-gfm';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

export async function validateMdx(content) {
  const body = content.replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/, '');
  await compile(body, { remarkPlugins: [remarkGfm] });
}

async function walk(directory) {
  let entries;
  try { entries = await readdir(directory, { withFileTypes: true }); }
  catch (error) { if (error.code === 'ENOENT') return []; throw error; }
  const files = [];
  for (const entry of entries) {
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await walk(filename));
    else if (entry.name.endsWith('.mdx')) files.push(filename);
  }
  return files.sort();
}

async function main() {
  const root = path.resolve(process.argv[2] || '.');
  const config = JSON.parse(await readFile(path.join(root, 'docs.json'), 'utf8'));
  const failures = [];
  let count = 0;
  const languages = new Set(config.navigation.languages.map(({ language }) => language));
  for (const entry of await readdir(root, { withFileTypes: true })) {
    if (entry.isDirectory() && !entry.name.startsWith('.')) languages.add(entry.name);
  }
  for (const language of languages) {
    for (const folder of ['guides', 'mcp']) {
      for (const filename of await walk(path.join(root, language, folder))) {
        count++;
        try { await validateMdx(await readFile(filename, 'utf8')); }
        catch (error) { failures.push(`${path.relative(root, filename)}: ${error.reason || error.message}`); }
      }
    }
  }
  for (const failure of failures) console.error(failure);
  console.log(`MDX syntax: ${count - failures.length}/${count} pages valid`);
  if (failures.length) process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  await main();
}
