import argparse
import json
import logging

from aiohttp import ClientSession, web


HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Camisole Judge Web UI</title>
  <style>
    :root {
      --bg: #f6f1e7;
      --card: #fffdf9;
      --ink: #1f1a17;
      --muted: #6a5e56;
      --accent: #ab3b2a;
      --accent-2: #315f72;
      --border: #e9dcc8;
      --ok: #2f6d3d;
      --err: #a22c2c;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      font-family: "Lora", "Georgia", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 20% 20%, #fdf7ed 0%, transparent 35%),
        radial-gradient(circle at 80% 0%, #f2e4d0 0%, transparent 45%),
        var(--bg);
      min-height: 100vh;
      padding: 24px;
    }

    .layout {
      max-width: 1100px;
      margin: 0 auto;
      display: grid;
      gap: 16px;
      grid-template-columns: 1fr;
    }

    @media (min-width: 960px) {
      .layout {
        grid-template-columns: 1fr 1fr;
      }
    }

    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      box-shadow: 0 10px 24px rgba(73, 50, 29, 0.08);
      animation: rise 0.35s ease;
    }

    @keyframes rise {
      from { transform: translateY(8px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }

    h1 {
      margin: 0 0 12px;
      font-size: 1.8rem;
      letter-spacing: 0.02em;
    }

    p {
      margin: 0;
      color: var(--muted);
    }

    .row {
      margin-top: 14px;
      display: grid;
      gap: 10px;
    }

    label {
      font-weight: 700;
      font-size: 0.92rem;
    }

    select,
    input,
    textarea,
    button {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 11px;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }

    textarea {
      min-height: 140px;
      resize: vertical;
      font-family: "Fira Code", "Menlo", monospace;
      font-size: 0.92rem;
      line-height: 1.45;
    }

    button {
      background: linear-gradient(135deg, var(--accent), #cf5139);
      color: #fff;
      border: none;
      cursor: pointer;
      font-weight: 700;
      transition: transform 0.14s ease, box-shadow 0.14s ease;
    }

    button:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 16px rgba(171, 59, 42, 0.24);
    }

    .split {
      display: grid;
      gap: 10px;
      grid-template-columns: 1fr;
    }

    .triple {
      display: grid;
      gap: 10px;
      grid-template-columns: 1fr;
    }

    @media (min-width: 640px) {
      .split {
        grid-template-columns: 1fr 1fr;
      }

      .triple {
        grid-template-columns: 1fr 1fr 1fr;
      }
    }

    .fieldset {
      border: 1px dashed var(--border);
      border-radius: 10px;
      padding: 10px;
      margin-top: 8px;
      background: #fffdfb;
    }

    .fieldset h3 {
      margin: 0 0 8px;
      font-size: 0.96rem;
      color: var(--accent-2);
    }

    .checkbox {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 700;
      color: var(--ink);
    }

    .checkbox input {
      width: auto;
      margin: 0;
    }

    .hidden {
      display: none;
    }

    .hint {
      color: var(--muted);
      font-size: 0.86rem;
    }

    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: "Fira Code", "Menlo", monospace;
      font-size: 0.92rem;
      line-height: 1.42;
      background: #f8f5ef;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      min-height: 280px;
    }

    .status {
      margin-bottom: 8px;
      font-weight: 700;
    }

    .subtitle {
      margin: 0 0 8px;
      font-weight: 700;
      color: var(--accent-2);
      font-size: 0.92rem;
    }

    .status.ok {
      color: var(--ok);
    }

    .status.err {
      color: var(--err);
    }

    .topline {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 10px;
    }

    .judge-label {
      color: var(--accent-2);
      font-weight: 700;
      font-size: 0.9rem;
    }
  </style>
</head>
<body>
  <div class="layout">
    <section class="card">
      <div class="topline">
        <h1>Camisole Judge Runner</h1>
        <div id="judgeUrl" class="judge-label"></div>
      </div>
      <p>Build a payload in one of the modes below, then send it to the judge /run endpoint.</p>

      <div class="row">
        <label for="mode">Mode</label>
        <select id="mode">
          <option value="simple">Simple run</option>
          <option value="tests">Run with tests JSON</option>
          <option value="interactive">Interactive judge</option>
          <option value="advanced">Advanced (all options)</option>
          <option value="raw">Raw payload JSON</option>
        </select>
      </div>

      <div class="row split">
        <div>
          <label for="lang">User language</label>
          <input id="lang" value="python" />
        </div>
        <div id="judgeLangWrap" class="hidden">
          <label for="judge_lang">Judge language</label>
          <input id="judge_lang" value="python" />
        </div>
      </div>

      <div class="row">
        <label for="source">User source</label>
        <textarea id="source">print(42)</textarea>
      </div>

      <div id="testsWrap" class="row hidden">
        <label for="tests">Tests (JSON array)</label>
        <textarea id="tests">[{"name": "test000", "stdin": "", "stdout": "42\n"}]</textarea>
        <div class="hint">Leave empty to omit tests.</div>
      </div>

      <div id="judgeSourceWrap" class="row hidden">
        <label for="judge_source">Judge source</label>
        <textarea id="judge_source">import sys\nline = sys.stdin.readline()\nprint(line.strip())</textarea>
        <div class="split">
          <div>
            <label for="stdin_user">stdin_user (initial input for user)</label>
            <textarea id="stdin_user" placeholder="Optional initial stdin for user code"></textarea>
          </div>
          <div>
            <label for="stdin_judge">stdin_judge (initial input for judge)</label>
            <textarea id="stdin_judge" placeholder="Optional initial stdin for judge code"></textarea>
          </div>
        </div>
      </div>

      <div id="advancedWrap" class="row hidden">
        <div class="fieldset">
          <h3>Global</h3>
          <label class="checkbox" for="all_fatal">
            <input id="all_fatal" type="checkbox" />
            <span>all_fatal</span>
          </label>
        </div>

        <div class="fieldset">
          <h3>compile (isolate options)</h3>
          <div class="triple">
            <input id="compile_time" placeholder="time (seconds)" />
            <input id="compile_wall-time" placeholder="wall-time (seconds)" />
            <input id="compile_extra-time" placeholder="extra-time (seconds)" />
            <input id="compile_mem" placeholder="mem (kB)" />
            <input id="compile_virt-mem" placeholder="virt-mem (kB)" />
            <input id="compile_fsize" placeholder="fsize (kB)" />
            <input id="compile_processes" placeholder="processes" />
            <input id="compile_stack" placeholder="stack (kB)" />
            <input id="compile_quota" placeholder="quota (blocks,inodes)" />
          </div>
        </div>

        <div class="fieldset">
          <h3>execute (global defaults for tests)</h3>
          <div class="row">
            <label for="execute_stdin">execute.stdin</label>
            <textarea id="execute_stdin" placeholder="stdin passed to program for each test"></textarea>
          </div>
          <div class="split">
            <div>
              <label for="execute_stdin_user">execute.stdin_user</label>
              <textarea id="execute_stdin_user" placeholder="default initial stdin for user (interactive)"></textarea>
            </div>
            <div>
              <label for="execute_stdin_judge">execute.stdin_judge</label>
              <textarea id="execute_stdin_judge" placeholder="default initial stdin for judge (interactive)"></textarea>
            </div>
          </div>
          <label class="checkbox" for="execute_judge">
            <input id="execute_judge" type="checkbox" />
            <span>execute.judge</span>
          </label>
          <div class="triple">
            <input id="execute_time" placeholder="time (seconds)" />
            <input id="execute_wall-time" placeholder="wall-time (seconds)" />
            <input id="execute_extra-time" placeholder="extra-time (seconds)" />
            <input id="execute_mem" placeholder="mem (kB)" />
            <input id="execute_virt-mem" placeholder="virt-mem (kB)" />
            <input id="execute_fsize" placeholder="fsize (kB)" />
            <input id="execute_processes" placeholder="processes" />
            <input id="execute_stack" placeholder="stack (kB)" />
            <input id="execute_quota" placeholder="quota (blocks,inodes)" />
          </div>
        </div>

        <div class="fieldset">
          <h3>Request-level interactive judge</h3>
          <div class="split">
            <input id="judge_lang_adv" placeholder="judge_lang" value="python" />
            <input id="judge_fault_exitcode" placeholder="judge_fault_exitcode (int)" />
          </div>
          <div class="row">
            <label for="judge_source_adv">judge_source</label>
            <textarea id="judge_source_adv" placeholder="judge source code"></textarea>
          </div>
            <div class="split">
              <div>
                <label for="stdin_user_adv">stdin_user</label>
                <textarea id="stdin_user_adv" placeholder="request-level initial stdin for user"></textarea>
              </div>
              <div>
                <label for="stdin_judge_adv">stdin_judge</label>
                <textarea id="stdin_judge_adv" placeholder="request-level initial stdin for judge"></textarea>
              </div>
            </div>
          <div class="triple">
            <input id="judge_compile_time" placeholder="judge_compile.time (seconds)" />
            <input id="judge_compile_wall-time" placeholder="judge_compile.wall-time (seconds)" />
            <input id="judge_compile_extra-time" placeholder="judge_compile.extra-time (seconds)" />
            <input id="judge_compile_mem" placeholder="judge_compile.mem (kB)" />
            <input id="judge_compile_virt-mem" placeholder="judge_compile.virt-mem (kB)" />
            <input id="judge_compile_fsize" placeholder="judge_compile.fsize (kB)" />
            <input id="judge_compile_processes" placeholder="judge_compile.processes" />
            <input id="judge_compile_stack" placeholder="judge_compile.stack (kB)" />
            <input id="judge_compile_quota" placeholder="judge_compile.quota (blocks,inodes)" />
          </div>
        </div>

        <div class="fieldset">
          <h3>tests (full JSON array, supports all per-test options)</h3>
          <textarea id="tests_advanced">[
  {
    "name": "test000",
    "stdin": "",
    "stdin_user": "",
    "stdin_judge": "",
    "fatal": false,
    "judge": true,
    "time": 1,
    "wall-time": 2,
    "extra-time": 0.2,
    "mem": 65536,
    "virt-mem": 131072,
    "fsize": 1024,
    "processes": 64,
    "stack": 8192,
    "quota": "10000,200",
    "judge_fault_exitcode": 42,
    "firewall_rules": {
      "allowed_chars": "[a-zA-Z0-9\\\\s\\\\n]",
      "max_line_length": 4096,
      "max_total_bytes": 65536,
      "format_rules": [],
      "violation_action": "STOP"
    },
    "user_execution": {
      "time": 1,
      "wall-time": 2,
      "mem": 65536
    },
    "judge_execution": {
      "time": 1,
      "wall-time": 2,
      "mem": 65536
    }
  }
]</textarea>
          <div class="hint">This textarea supports all per-test keys from schema: name, fatal, stdin, stdin_user, stdin_judge, judge, isolate opts, judge_fault_exitcode, firewall_rules, user_execution, judge_execution.</div>
        </div>
      </div>

      <div id="rawWrap" class="row hidden">
        <label for="raw_payload">Raw payload JSON</label>
        <textarea id="raw_payload">{
  "lang": "python",
  "source": "print(42)"
}</textarea>
      </div>

      <div class="row">
        <div class="subtitle">Request Preview (live)</div>
        <pre id="requestPreview">{}</pre>
      </div>

      <div class="row">
        <button id="runBtn">Send to /run</button>
      </div>
    </section>

    <section class="card">
      <div id="status" class="status">Idle</div>
      <pre id="result">{}</pre>
    </section>
  </div>

  <script>
    const modeEl = document.getElementById("mode");
    const testsWrap = document.getElementById("testsWrap");
    const judgeSourceWrap = document.getElementById("judgeSourceWrap");
    const judgeLangWrap = document.getElementById("judgeLangWrap");
    const advancedWrap = document.getElementById("advancedWrap");
    const rawWrap = document.getElementById("rawWrap");
    const runBtn = document.getElementById("runBtn");
    const status = document.getElementById("status");
    const result = document.getElementById("result");
    const judgeUrl = document.getElementById("judgeUrl");
    const requestPreview = document.getElementById("requestPreview");

    fetch("/judge-url")
      .then((r) => r.json())
      .then((data) => { judgeUrl.textContent = "Judge: " + data.judge_url; })
      .catch(() => { judgeUrl.textContent = "Judge URL unavailable"; });

    function setMode(mode) {
      testsWrap.classList.toggle("hidden", mode !== "tests");
      judgeSourceWrap.classList.toggle("hidden", mode !== "interactive");
      judgeLangWrap.classList.toggle("hidden", mode !== "interactive");
      advancedWrap.classList.toggle("hidden", mode !== "advanced");
      rawWrap.classList.toggle("hidden", mode !== "raw");
    }

    modeEl.addEventListener("change", () => setMode(modeEl.value));
    setMode(modeEl.value);

    const ISOLATE_FIELDS = [
      ["time", false],
      ["wall-time", false],
      ["extra-time", false],
      ["mem", true],
      ["virt-mem", true],
      ["fsize", true],
      ["processes", true],
      ["stack", true],
      ["quota", null]
    ];

    function parseNumericInput(rawValue, integerOnly, fieldName) {
      const trimmed = rawValue.trim();
      if (!trimmed) {
        return null;
      }

      const value = integerOnly ? parseInt(trimmed, 10) : parseFloat(trimmed);
      if (Number.isNaN(value)) {
        throw new Error("Invalid number for " + fieldName);
      }
      return value;
    }

    function readIsolateOptions(prefix) {
      const options = {};

      for (const [fieldName, integerOnly] of ISOLATE_FIELDS) {
        const element = document.getElementById(prefix + fieldName);
        if (!element) {
          continue;
        }

        const value = element.value.trim();
        if (!value) {
          continue;
        }

        if (integerOnly === null) {
          options[fieldName] = value;
        } else {
          options[fieldName] = parseNumericInput(value, integerOnly, prefix + fieldName);
        }
      }

      return options;
    }

    function buildPayload() {
      const mode = modeEl.value;
      if (mode === "raw") {
        return JSON.parse(document.getElementById("raw_payload").value);
      }

      const payload = {
        lang: document.getElementById("lang").value,
        source: document.getElementById("source").value
      };

      if (mode === "tests") {
        const testsText = document.getElementById("tests").value.trim();
        if (testsText) {
          payload.tests = JSON.parse(testsText);
        }
      }

      if (mode === "interactive") {
        payload.judge_lang = document.getElementById("judge_lang").value;
        payload.judge_source = document.getElementById("judge_source").value;
        const stdinUser = document.getElementById("stdin_user").value;
        const stdinJudge = document.getElementById("stdin_judge").value;
        if (stdinUser.trim()) {
          payload.stdin_user = stdinUser;
        }
        if (stdinJudge.trim()) {
          payload.stdin_judge = stdinJudge;
        }
      }

      if (mode === "advanced") {
        const allFatal = document.getElementById("all_fatal").checked;
        if (allFatal) {
          payload.all_fatal = true;
        }

        const compileOpts = readIsolateOptions("compile_");
        if (Object.keys(compileOpts).length > 0) {
          payload.compile = compileOpts;
        }

        const executeOpts = readIsolateOptions("execute_");
        const executeStdin = document.getElementById("execute_stdin").value;
        const executeStdinUser = document.getElementById("execute_stdin_user").value;
        const executeStdinJudge = document.getElementById("execute_stdin_judge").value;
        const executeJudge = document.getElementById("execute_judge").checked;
        if (executeStdin.trim()) {
          executeOpts.stdin = executeStdin;
        }
        if (executeStdinUser.trim()) {
          executeOpts.stdin_user = executeStdinUser;
        }
        if (executeStdinJudge.trim()) {
          executeOpts.stdin_judge = executeStdinJudge;
        }
        if (executeJudge) {
          executeOpts.judge = true;
        }
        if (Object.keys(executeOpts).length > 0) {
          payload.execute = executeOpts;
        }

        const judgeLangAdv = document.getElementById("judge_lang_adv").value.trim();
        const judgeSourceAdv = document.getElementById("judge_source_adv").value;
        const stdinUserAdv = document.getElementById("stdin_user_adv").value;
        const stdinJudgeAdv = document.getElementById("stdin_judge_adv").value;
        const judgeFaultRaw = document.getElementById("judge_fault_exitcode").value;
        const judgeCompileOpts = readIsolateOptions("judge_compile_");

        if (judgeLangAdv) {
          payload.judge_lang = judgeLangAdv;
        }
        if (judgeSourceAdv.trim()) {
          payload.judge_source = judgeSourceAdv;
        }
        if (stdinUserAdv.trim()) {
          payload.stdin_user = stdinUserAdv;
        }
        if (stdinJudgeAdv.trim()) {
          payload.stdin_judge = stdinJudgeAdv;
        }
        if (judgeFaultRaw.trim()) {
          payload.judge_fault_exitcode = parseNumericInput(
            judgeFaultRaw,
            true,
            "judge_fault_exitcode"
          );
        }
        if (Object.keys(judgeCompileOpts).length > 0) {
          payload.judge_compile = judgeCompileOpts;
        }

        const testsAdvText = document.getElementById("tests_advanced").value.trim();
        if (testsAdvText) {
          payload.tests = JSON.parse(testsAdvText);
        }
      }

      return payload;
    }

    function refreshPreview() {
      try {
        requestPreview.textContent = JSON.stringify(buildPayload(), null, 2);
      } catch (error) {
        requestPreview.textContent = JSON.stringify({
          success: false,
          error: "Invalid payload while editing",
          details: String(error)
        }, null, 2);
      }
    }

    modeEl.addEventListener("change", refreshPreview);
    document.querySelectorAll("input, textarea, select").forEach((el) => {
      el.addEventListener("input", refreshPreview);
      el.addEventListener("change", refreshPreview);
    });
    refreshPreview();

    runBtn.addEventListener("click", async () => {
      status.textContent = "Running...";
      status.className = "status";

      try {
        const payload = buildPayload();
        const response = await fetch("/api/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        const body = await response.json();
        result.textContent = JSON.stringify(body, null, 2);

        const ok = response.ok && body.success !== false;
        status.textContent = ok ? "Success" : "Request failed";
        status.className = "status " + (ok ? "ok" : "err");
      } catch (error) {
        status.textContent = "Request failed";
        status.className = "status err";
        result.textContent = JSON.stringify({
          success: false,
          error: String(error)
        }, null, 2);
      }
    });
  </script>
</body>
</html>
"""


async def index_handler(request):
    return web.Response(text=HTML_PAGE, content_type='text/html')


async def judge_url_handler(request):
    return web.json_response({'judge_url': request.app['judge_url']})


async def run_proxy_handler(request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response(
            {'success': False, 'error': 'Malformed JSON payload'},
            status=400,
        )

    judge_url = request.app['judge_url']

    try:
        async with ClientSession() as session:
            async with session.post(judge_url, json=payload) as response:
                text = await response.text()
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    body = json.loads(text)
                else:
                    body = {
                        'success': False,
                        'error': 'Judge did not return JSON',
                        'status': response.status,
                        'raw': text,
                    }

                return web.json_response(body, status=response.status)
    except Exception as e:
        return web.json_response(
            {
                'success': False,
                'error': 'Cannot contact judge',
                'details': str(e),
            },
            status=502,
        )


def make_application(judge_url):
    app = web.Application()
    app['judge_url'] = judge_url
    app.router.add_get('/', index_handler)
    app.router.add_get('/judge-url', judge_url_handler)
    app.router.add_post('/api/run', run_proxy_handler)
    return app


def handle(args):
    app = make_application(args.judge_url)

    logging.info(
        'Starting web UI on http://%s:%d and proxying judge requests to %s',
        args.host,
        args.port,
        args.judge_url,
    )
    web.run_app(app, host=args.host, port=args.port)
    return 0


def build(parser):
    p = parser.add_parser('webui', add_help=False)

    p.add_argument('-h', '--host', default='127.0.0.1')
    p.add_argument('-p', '--port', type=int, default=42921)
    p.add_argument(
        '--judge-url',
        default='http://127.0.0.1:42920/run',
        help='complete URL of the judge /run endpoint',
    )
    p.add_argument('--help', action='help')

    return 'webui', handle


def main(argv=None):
    parser = argparse.ArgumentParser(
        add_help=False,
        description='Standalone Camisole /run web UI proxy',
    )
    parser.add_argument('-h', '--host', default='127.0.0.1')
    parser.add_argument('-p', '--port', type=int, default=42921)
    parser.add_argument(
        '--judge-url',
        default='http://127.0.0.1:42920/run',
        help='complete URL of the judge /run endpoint',
    )
    parser.add_argument('--help', action='help')

    return handle(parser.parse_args(argv))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()