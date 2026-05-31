import assert from 'node:assert/strict';
import { mkdtemp, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { loadRootEnv } from '../web/env-loader.js';

const dir = await mkdtemp(join(tmpdir(), 'radar-env-'));
await writeFile(
  join(dir, '.env'),
  [
    'YOUTUBE_CHANNEL_ID=UC123456789  # 頻道 ID',
    'TEST_INLINE_COMMENT_ID=UC123456789  # 頻道 ID',
    'THREADS_USER_ID=27869600595962634',
    'EXISTING_VALUE=from_file',
    'QUOTED_VALUE="hello # still text"',
  ].join('\n'),
  'utf8',
);

process.env.EXISTING_VALUE = 'from_process';
loadRootEnv(dir);

assert.equal(process.env.TEST_INLINE_COMMENT_ID, 'UC123456789');
assert.equal(process.env.THREADS_USER_ID, '27869600595962634');
assert.equal(process.env.EXISTING_VALUE, 'from_process');
assert.equal(process.env.QUOTED_VALUE, 'hello # still text');

console.log('web env loader ok');
