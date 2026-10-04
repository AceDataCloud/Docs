#!/usr/bin/env node
// Parse generated pages without evaluating any MDX/JSX or importing page code.
import { compile } from '@mdx-js/mdx';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import { readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

export async function validateMdx(content) {
  const body = content.replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/, '');
  const links = [];
  function collectLinks() {
    return (tree) => {
      function visit(node) {
        if (['link', 'image'].includes(node.type)) links.push(node.url);
        for (const attribute of node.attributes || []) {
          if (['href', 'src'].includes(attribute.name) && typeof attribute.value === 'string') links.push(attribute.value);
        }
        for (const child of node.children || []) visit(child);
      }
      visit(tree);
    };
  }
  await compile(body, { remarkPlugins: [remarkGfm, remarkMath, collectLinks] });
  return links;
}

export async function missingLocalLinks(root, filename, links) {
  const missing = [];
  for (const link of new Set(links)) {
    if (!link || /^(?:[a-z][a-z\d+.-]*:|\/\/|#)/i.test(link)) continue;
    const pathname = decodeURIComponent(link.split(/[?#]/, 1)[0]);
    if (!pathname) continue;
    const target = pathname.startsWith('/') ? path.join(root, pathname) : path.resolve(path.dirname(filename), pathname);
    const candidates = [target, `${target}.mdx`, `${target}.md`, path.join(target, 'index.mdx')];
    let found = false;
    for (const candidate of candidates) {
      if (path.relative(root, candidate).startsWith('..')) continue;
      try { if ((await stat(candidate)).isFile()) { found = true; break; } }
      catch (error) { if (!['ENOENT', 'ENOTDIR'].includes(error.code)) throw error; }
    }
    if (!found) missing.push(link);
  }
  return missing;
}

async function walk(directory) {
  let entries;
  try { entries = await readdir(directory, { withFileTypes: true }); }
  catch (error) { if (error.code === 'ENOENT') return []; throw error; }
  const files = [];
  for (const entry of entries) {
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory() && !entry.name.startsWith('.') && entry.name !== 'node_modules') files.push(...await walk(filename));
    else if (entry.name.endsWith('.mdx')) files.push(filename);
  }
  return files.sort();
}

async function main() {
  const root = path.resolve(process.argv[2] || '.');
  const failures = [];
  let count = 0;
  for (const filename of await walk(root)) {
    count++;
    try {
      const links = await validateMdx(await readFile(filename, 'utf8'));
      const missing = await missingLocalLinks(root, filename, links);
      if (missing.length) failures.push(`${path.relative(root, filename)}: missing links ${missing.join(', ')}`);
    }
    catch (error) { failures.push(`${path.relative(root, filename)}: ${error.reason || error.message}`); }
  }
  for (const failure of failures) console.error(failure);
  console.log(`MDX syntax and local links: ${count - failures.length}/${count} pages valid`);
  if (failures.length) process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  await main();
}
