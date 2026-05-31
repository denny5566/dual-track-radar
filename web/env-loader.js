import { existsSync, readFileSync } from 'fs';
import { join } from 'path';

function stripInlineComment(value) {
  let quote = '';
  for (let i = 0; i < value.length; i += 1) {
    const ch = value[i];
    if ((ch === '"' || ch === "'") && value[i - 1] !== '\\') {
      quote = quote === ch ? '' : ch;
    }
    if (ch === '#' && !quote && /\s/.test(value[i - 1] || '')) {
      return value.slice(0, i).trim();
    }
  }
  return value.trim();
}

function unquote(value) {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

export function loadRootEnv(rootDir) {
  const envPath = join(rootDir, '.env');
  if (!existsSync(envPath)) return;

  const lines = readFileSync(envPath, 'utf8').split(/\r?\n/);
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;

    const eq = line.indexOf('=');
    if (eq <= 0) continue;

    const key = line.slice(0, eq).trim();
    const rawValue = line.slice(eq + 1);
    if (!key || Object.prototype.hasOwnProperty.call(process.env, key)) continue;

    process.env[key] = unquote(stripInlineComment(rawValue));
  }
}
