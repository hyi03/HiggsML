import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {checkSource} from './check-source.mjs';
import {checkDisplay} from './check-display.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
for(const arg of process.argv.slice(2))if(arg!=='--source-only')throw new Error('Unsupported option '+arg+'; this checker validates the current basic report, not historical run aggregates.');
checkSource(root);
if(!process.argv.includes('--source-only'))checkDisplay(root);
console.log('Scope: report/source and website checks only; original run aggregates and scientific validity are not reverified.');
