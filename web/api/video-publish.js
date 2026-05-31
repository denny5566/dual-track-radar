/**
 * VM-only dashboard endpoint for YouTube video publishing.
 * Calls the Python helper because the VM owns the video files, SQLite DB, and OAuth env.
 */

import { execFile, spawn } from 'child_process';
import { dirname, join, resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = resolve(__dirname, '..', '..');
const HELPER = join(ROOT_DIR, 'dashboard_video_publish.py');
const PYTHON = process.env.PYTHON || process.env.PYTHON_BIN || 'python';

function runHelper(action) {
  return new Promise((resolvePromise) => {
    execFile(
      PYTHON,
      [HELPER, action],
      {
        cwd: ROOT_DIR,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        timeout: action === 'publish-youtube' ? 15 * 60 * 1000 : 30 * 1000,
        maxBuffer: 1024 * 1024,
      },
      (error, stdout, stderr) => {
        const lines = stdout.trim().split(/\r?\n/).filter(Boolean);
        const lastLine = lines[lines.length - 1] || '{}';
        let payload;
        try {
          payload = JSON.parse(lastLine);
        } catch {
          payload = {
            ok: false,
            state: 'bad_helper_output',
            error: 'Python helper did not return JSON',
            stdout,
            stderr,
          };
        }

        if (error && payload.ok !== true) {
          payload.exitCode = error.code || 1;
          payload.stderr = stderr;
        }
        resolvePromise(payload);
      },
    );
  });
}

function startRenderJob() {
  const child = spawn(PYTHON, [HELPER, 'render-youtube'], {
    cwd: ROOT_DIR,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    detached: true,
    stdio: 'ignore',
  });
  child.unref();
}

export default async function handler(req, res) {
  const action = req.params?.action || '';

  if (req.method === 'GET') {
    const result = await runHelper('status');
    return res.status(result.ok ? 200 : 500).json(result);
  }

  if (req.method === 'POST' && action === 'render') {
    const current = await runHelper('status');
    if (current.render?.state === 'rendering') {
      return res.status(200).json({ ok: true, ...current });
    }
    startRenderJob();
    return res.status(202).json({
      ok: true,
      state: 'rendering',
      render: { state: 'rendering', stage: '準備報告資料', percent: 10, error: '' },
    });
  }

  if (req.method === 'POST') {
    const result = await runHelper('publish-youtube');
    return res.status(result.ok ? 200 : 400).json(result);
  }

  res.setHeader('Allow', 'GET, POST');
  return res.status(405).json({ ok: false, error: 'Method not allowed' });
}
