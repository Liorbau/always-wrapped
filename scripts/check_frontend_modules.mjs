// Walks the ES module graph from each page entry point and fails if an import
// path is missing or a named import is not actually exported. Browsers only
// surface these at load time, and this project has no bundler to catch them.
//
//   node scripts/check_frontend_modules.mjs

import { existsSync, readFileSync } from 'node:fs';
import { dirname, relative, resolve } from 'node:path';

const ENTRY_POINTS = ['static/src/main.js', 'static/src/observatory.js'];
const IMPORT_RE = /import\s+([^'"]+?)\s+from\s+['"]([^'"]+)['"]/g;

const problems = [];
const visited = new Set();

function exportedNames(source) {
    const names = new Set();
    for (const match of source.matchAll(/export\s+(?:async\s+)?function\s+(\w+)/g)) {
        names.add(match[1]);
    }
    for (const match of source.matchAll(/export\s+class\s+(\w+)/g)) names.add(match[1]);
    for (const match of source.matchAll(/export\s+(?:const|let|var)\s+(\w+)/g)) {
        names.add(match[1]);
    }
    for (const match of source.matchAll(/export\s*\{([^}]+)\}/g)) {
        for (const part of match[1].split(',')) {
            const name = part.trim().split(/\s+as\s+/).pop().trim();
            if (name) names.add(name);
        }
    }
    return names;
}

function parseClause(clause) {
    const namespace = clause.match(/^\*\s+as\s+\w+$/);
    if (namespace) return { namespace: true, names: [] };
    const braced = clause.match(/\{([^}]*)\}/);
    if (!braced) return { namespace: false, names: [] };  // default import
    const names = braced[1]
        .split(',')
        .map((part) => part.trim().split(/\s+as\s+/)[0].trim())
        .filter(Boolean);
    return { namespace: false, names };
}

function walk(file) {
    if (visited.has(file)) return;
    visited.add(file);

    if (!existsSync(file)) {
        problems.push(`missing module: ${relative('.', file)}`);
        return;
    }
    const source = readFileSync(file, 'utf8');

    for (const [, clause, specifier] of source.matchAll(IMPORT_RE)) {
        if (!specifier.startsWith('.')) continue;  // bare specifiers need a bundler
        const target = resolve(dirname(file), specifier);
        const here = relative('.', file);

        if (!existsSync(target)) {
            problems.push(`${here}: imports missing file '${specifier}'`);
            continue;
        }
        const { namespace, names } = parseClause(clause);
        if (!namespace) {
            const available = exportedNames(readFileSync(target, 'utf8'));
            for (const name of names) {
                if (!available.has(name)) {
                    problems.push(`${here}: '${name}' is not exported by '${specifier}'`);
                }
            }
        }
        walk(target);
    }
}

for (const entry of ENTRY_POINTS) walk(resolve(entry));

if (problems.length) {
    console.error('Frontend module graph problems:');
    for (const problem of problems) console.error(`  - ${problem}`);
    process.exit(1);
}
console.log(`OK: ${visited.size} modules resolve from ${ENTRY_POINTS.length} entry points`);
