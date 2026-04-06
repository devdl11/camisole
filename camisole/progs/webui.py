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

    .tests-toolbar {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .tests-toolbar button {
      width: auto;
      min-width: 128px;
      padding: 8px 10px;
      font-size: 0.9rem;
      border-radius: 9px;
    }

    .tests-toolbar .secondary {
      background: linear-gradient(135deg, #466473, #2f4b58);
    }

    .test-card {
      border: 1px solid var(--border);
      border-radius: 11px;
      padding: 10px;
      background: #fff;
      display: grid;
      gap: 10px;
    }

    .test-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
    }

    .test-card-header .title {
      font-weight: 700;
      color: var(--accent-2);
      font-size: 0.92rem;
    }

    .test-card-header .remove {
      width: auto;
      background: linear-gradient(135deg, #8d3025, #b53b2d);
      padding: 7px 10px;
      font-size: 0.85rem;
    }

    .test-advanced {
      border-top: 1px dashed var(--border);
      padding-top: 10px;
      display: grid;
      gap: 10px;
    }

    .mini-title {
      margin: 0;
      color: var(--muted);
      font-weight: 700;
      font-size: 0.85rem;
    }

    .defaults-grid {
      display: grid;
      gap: 10px;
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
          <option value="tests">Run with tests</option>
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
        <div class="hint">Use the test-case builder below to configure tests with form fields.</div>
      </div>

      <div id="judgeSourceWrap" class="row hidden">
        <label for="judge_source">Judge source</label>
        <textarea id="judge_source">import sys\nline = sys.stdin.readline()\nprint(line.strip())</textarea>
      </div>

      <div id="advancedWrap" class="row hidden">
        <div class="fieldset">
          <h3>Global</h3>
          <label class="checkbox" for="all_fatal">
            <input id="all_fatal" type="checkbox" />
            <span>all_fatal</span>
          </label>
          <label class="checkbox" for="debug_isolate">
            <input id="debug_isolate" type="checkbox" />
            <span>debug_isolate (include isolate stdout/stderr)</span>
          </label>
        </div>

        <div class="fieldset">
          <h3>compile (isolate options)</h3>
          <div class="triple">
            <input id="compile_time" placeholder="time (ms)" />
            <input id="compile_wall-time" placeholder="wall-time (ms)" />
            <input id="compile_extra-time" placeholder="extra-time (ms)" />
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
          <div class="triple">
            <input id="execute_time" placeholder="time (ms)" />
            <input id="execute_wall-time" placeholder="wall-time (ms)" />
            <input id="execute_extra-time" placeholder="extra-time (ms)" />
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
          <div class="triple">
            <input id="judge_compile_time" placeholder="judge_compile.time (ms)" />
            <input id="judge_compile_wall-time" placeholder="judge_compile.wall-time (ms)" />
            <input id="judge_compile_extra-time" placeholder="judge_compile.extra-time (ms)" />
            <input id="judge_compile_mem" placeholder="judge_compile.mem (kB)" />
            <input id="judge_compile_virt-mem" placeholder="judge_compile.virt-mem (kB)" />
            <input id="judge_compile_fsize" placeholder="judge_compile.fsize (kB)" />
            <input id="judge_compile_processes" placeholder="judge_compile.processes" />
            <input id="judge_compile_stack" placeholder="judge_compile.stack (kB)" />
            <input id="judge_compile_quota" placeholder="judge_compile.quota (blocks,inodes)" />
          </div>
        </div>

      </div>

      <div id="testsBuilderWrap" class="row hidden">
        <div class="subtitle">Tests Builder</div>
        <div class="fieldset defaults-grid" id="testsDefaultsWrap">
          <h3>Global defaults for all tests</h3>
          <label class="checkbox" for="tests_defaults_all_fatal">
            <input id="tests_defaults_all_fatal" type="checkbox" />
            <span>all_fatal (stop on first failing test)</span>
          </label>
          <div class="triple">
            <input id="tests_defaults_time" placeholder="default time (ms)" />
            <input id="tests_defaults_wall-time" placeholder="default wall-time (ms)" />
            <input id="tests_defaults_extra-time" placeholder="default extra-time (ms)" />
            <input id="tests_defaults_mem" placeholder="default mem (kB)" />
            <input id="tests_defaults_virt-mem" placeholder="default virt-mem (kB)" />
            <input id="tests_defaults_fsize" placeholder="default fsize (kB)" />
            <input id="tests_defaults_processes" placeholder="default processes" />
            <input id="tests_defaults_stack" placeholder="default stack (kB)" />
            <input id="tests_defaults_quota" placeholder="default quota (blocks,inodes)" />
          </div>
          <div class="hint">Units: time fields are in ms in the UI (converted to seconds in payload), memory fields are in kB.</div>
        </div>
        <div class="tests-toolbar">
          <button id="addTestBtn" type="button">+ Add test</button>
          <button id="removeTestBtn" type="button" class="secondary">- Remove last</button>
        </div>
        <div id="testsList" class="row"></div>
        <div class="hint">In advanced mode, each test card exposes all supported per-test fields.</div>
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
    const testsBuilderWrap = document.getElementById("testsBuilderWrap");
    const testsList = document.getElementById("testsList");
    const testsDefaultsWrap = document.getElementById("testsDefaultsWrap");
    const addTestBtn = document.getElementById("addTestBtn");
    const removeTestBtn = document.getElementById("removeTestBtn");
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

    const ISOLATE_FIELD_TYPES = Object.fromEntries(ISOLATE_FIELDS);
    const TIME_FIELDS = new Set(["time", "wall-time", "extra-time"]);

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

    function parseIsolateFieldValue(fieldName, rawValue, integerOnly, sourceName) {
      const trimmed = rawValue.trim();
      if (!trimmed) {
        return null;
      }

      if (integerOnly === null) {
        return trimmed;
      }

      const numeric = parseNumericInput(trimmed, integerOnly, sourceName);

      // UI uses ms for time-like fields; API expects seconds.
      if (TIME_FIELDS.has(fieldName)) {
        return numeric / 1000.0;
      }

      return numeric;
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

        options[fieldName] = parseIsolateFieldValue(
          fieldName,
          value,
          integerOnly,
          prefix + fieldName
        );
      }

      return options;
    }

    function readIsolateOptionsFromCard(card, prefix) {
      const options = {};
      card.querySelectorAll('[data-iso-prefix="' + prefix + '"]').forEach((el) => {
        const fieldName = el.getAttribute("data-iso-field");
        const integerOnly = ISOLATE_FIELD_TYPES[fieldName];
        const value = el.value.trim();
        if (!value) {
          return;
        }

          options[fieldName] = parseIsolateFieldValue(
            fieldName,
            value,
            integerOnly,
            prefix + "." + fieldName
          );
      });
      return options;
    }

    function setMode(mode) {
      testsWrap.classList.toggle("hidden", mode !== "tests");
      judgeSourceWrap.classList.toggle("hidden", mode !== "interactive");
      judgeLangWrap.classList.toggle("hidden", mode !== "interactive");
      advancedWrap.classList.toggle("hidden", mode !== "advanced");
      testsBuilderWrap.classList.toggle("hidden", !(mode === "tests" || mode === "advanced"));
      rawWrap.classList.toggle("hidden", mode !== "raw");
      updateTestsAdvancedVisibility();
      updateJudgeOptionVisibility();
    }

    function hasJudgeConfiguration() {
      if (modeEl.value === "interactive") {
        return true;
      }
      if (modeEl.value === "advanced") {
        const jl = document.getElementById("judge_lang_adv").value.trim();
        const js = document.getElementById("judge_source_adv").value.trim();
        return Boolean(jl && js);
      }
      return false;
    }

    function updateJudgeOptionVisibility() {
      const showJudgeOptions = hasJudgeConfiguration();
      testsDefaultsWrap.querySelectorAll(".judge-only").forEach((el) => {
        el.classList.toggle("hidden", !showJudgeOptions);
      });
      testsList.querySelectorAll(".judge-only").forEach((el) => {
        el.classList.toggle("hidden", !showJudgeOptions);
      });
      testsList.querySelectorAll(".shared-only").forEach((el) => {
        el.classList.toggle("hidden", !showJudgeOptions);
      });
    }

    function readGlobalTestDefaults() {
      const defaults = readIsolateOptions("tests_defaults_");
      const defaultsAllFatal = document.getElementById("tests_defaults_all_fatal").checked;

      return {
        allFatal: defaultsAllFatal,
        executeDefaults: defaults,
      };
    }

    function isolateInputsHtml(prefix) {
      return ISOLATE_FIELDS.map(([name]) => (
        '<input data-iso-prefix="' + prefix + '" data-iso-field="' + name + '" placeholder="' + prefix + '.' + name +
          (TIME_FIELDS.has(name) ? ' (ms)' : (name === 'mem' || name === 'virt-mem' || name === 'fsize' || name === 'stack' ? ' (kB)' : '')) +
        '" />'
      )).join('');
    }

    function createTestCard(index) {
      const card = document.createElement("div");
      card.className = "test-card";
      card.innerHTML =
        '<div class="test-card-header">' +
          '<div class="title">Test #' + (index + 1) + '</div>' +
          '<button type="button" class="remove">Remove</button>' +
        '</div>' +
        '<div class="split">' +
          '<input class="t-name" placeholder="name (e.g. test000)" />' +
          '<label class="checkbox"><input type="checkbox" class="t-fatal" /><span>fatal</span></label>' +
        '</div>' +
        '<div class="row">' +
          '<label>stdin</label>' +
          '<textarea class="t-stdin" placeholder="Standard input for this test"></textarea>' +
        '</div>' +
        '<div class="row">' +
          '<label>expected stdout (optional)</label>' +
          '<textarea class="t-expected" placeholder="If set, stdout must match exactly"></textarea>' +
        '</div>' +
        '<div class="split">' +
            '<div class="judge-only"><label>stdin_judge</label><textarea class="t-stdin-judge" placeholder="Initial stdin for judge"></textarea></div>' +
        '</div>' +
          '<label class="checkbox judge-only"><input type="checkbox" class="t-judge" checked /><span>use judge for this test</span></label>' +
        '<div class="test-advanced hidden">' +
          '<div class="mini-title shared-only">Per-test isolate options</div>' +
          '<div class="triple shared-only">' + isolateInputsHtml('t') + '</div>' +
            '<div class="split judge-only">' +
            '<select class="f-action"><option value="STOP">firewall violation_action: ERROR</option><option value="WARN">firewall violation_action: WARN</option></select>' +
            '<label class="checkbox"><input type="checkbox" class="t-io-transcript" /><span>record io_transcript</span></label>' +
          '</div>' +
            '<div class="mini-title judge-only">firewall_rules</div>' +
            '<div class="split judge-only">' +
            '<input class="f-allowed" placeholder="allowed_chars regex" />' +
            '<input class="f-format" placeholder="format_rules (comma separated)" />' +
          '</div>' +
            '<div class="split judge-only">' +
            '<input class="f-max-line" placeholder="max_line_length" />' +
            '<input class="f-max-total" placeholder="max_total_bytes" />' +
          '</div>' +
          '<div class="mini-title">user_execution isolate options</div>' +
          '<div class="triple">' + isolateInputsHtml('ue') + '</div>' +
            '<div class="mini-title judge-only">judge_execution isolate options</div>' +
            '<div class="triple judge-only">' + isolateInputsHtml('je') + '</div>' +
        '</div>';

      card.querySelector(".remove").addEventListener("click", () => {
        card.remove();
        if (!testsList.querySelector(".test-card")) {
          testsList.appendChild(createTestCard(0));
        }
        renumberTests();
        refreshPreview();
      });

      return card;
    }

    function renumberTests() {
      const cards = testsList.querySelectorAll(".test-card");
      cards.forEach((card, idx) => {
        card.querySelector(".title").textContent = "Test #" + (idx + 1);
      });
      removeTestBtn.disabled = cards.length <= 1;
      updateJudgeOptionVisibility();
    }

    function updateTestsAdvancedVisibility() {
      const isAdvanced = modeEl.value === "advanced";
      testsList.querySelectorAll(".test-advanced").forEach((el) => {
        el.classList.toggle("hidden", !isAdvanced);
      });
    }

    function collectTests(advancedMode) {
      const tests = [];
      const cards = testsList.querySelectorAll(".test-card");
      const judgeConfigured = hasJudgeConfiguration();
      cards.forEach((card) => {
        const test = {};

        const name = card.querySelector(".t-name").value.trim();
        const stdin = card.querySelector(".t-stdin").value;
        const expected = card.querySelector(".t-expected").value;
        const stdinJudge = card.querySelector(".t-stdin-judge").value;
        const ioTranscript = card.querySelector(".t-io-transcript").checked;
        const fatal = card.querySelector(".t-fatal").checked;
        const judge = card.querySelector(".t-judge").checked;

        if (name) {
          test.name = name;
        }
        if (stdin) {
          test.stdin = stdin;
        }
        if (expected) {
          test.expected = expected;
        }
        if (stdinJudge) {
          // mapped later inside nested test.judge config
        }
        if (fatal) {
          test.fatal = true;
        }

        if (advancedMode) {
          if (judgeConfigured) {
            const judgeObject = { judge };

            const testIsolate = readIsolateOptionsFromCard(card, "t");
            Object.assign(test, testIsolate);

            const allowedChars = card.querySelector(".f-allowed").value.trim();
            const formatRules = card.querySelector(".f-format").value.trim();
            const maxLine = card.querySelector(".f-max-line").value.trim();
            const maxTotal = card.querySelector(".f-max-total").value.trim();
            const action = card.querySelector(".f-action").value;
            const firewall = {};

            if (allowedChars) {
              firewall.allowed_chars = allowedChars;
            }
            if (formatRules) {
              firewall.format_rules = formatRules.split(',').map((r) => r.trim()).filter((r) => r);
            }
            if (maxLine) {
              firewall.max_line_length = parseNumericInput(maxLine, true, "tests[].firewall.max_line_length");
            }
            if (maxTotal) {
              firewall.max_total_bytes = parseNumericInput(maxTotal, true, "tests[].firewall.max_total_bytes");
            }
            if (action) {
              firewall.violation_action = action;
            }

            if (Object.keys(firewall).length > 0) {
              judgeObject.firewall_rules = firewall;
            }

            if (stdinJudge) {
              judgeObject.stdin_judge = stdinJudge;
            }

            if (ioTranscript) {
              judgeObject.io_transcript = true;
            }

            test.judge = judgeObject;
          }
        }

        const userExecution = readIsolateOptionsFromCard(card, "ue");
        if (Object.keys(userExecution).length > 0) {
          if (judgeConfigured) {
            test.user_execution = userExecution;
          } else {
            Object.assign(test, userExecution);
          }
        }

        if (advancedMode && judgeConfigured) {
          const judgeExecution = readIsolateOptionsFromCard(card, "je");
          if (Object.keys(judgeExecution).length > 0) {
            if (!test.judge) {
              test.judge = { judge: true };
            }
            test.judge.judge_execution = judgeExecution;
          }
        }

        if (Object.keys(test).length > 0) {
          tests.push(test);
        }
      });

      return tests;
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
        const defaults = readGlobalTestDefaults();

        if (defaults.allFatal) {
          payload.all_fatal = true;
        }
        if (Object.keys(defaults.executeDefaults).length > 0) {
          payload.execute = defaults.executeDefaults;
        }

        const tests = collectTests(false);
        if (tests.length > 0) {
          payload.tests = tests;
        }
      }

      if (mode === "interactive") {
        payload.judge_lang = document.getElementById("judge_lang").value;
        payload.judge_source = document.getElementById("judge_source").value;
      }

      if (mode === "advanced") {
        const defaults = readGlobalTestDefaults();
        if (defaults.allFatal) {
          payload.all_fatal = true;
        }

        const allFatal = document.getElementById("all_fatal").checked;
        if (allFatal) {
          payload.all_fatal = true;
        }

        const debugIsolate = document.getElementById("debug_isolate").checked;
        if (debugIsolate) {
          payload.debug_isolate = true;
        }

        const compileOpts = readIsolateOptions("compile_");
        if (Object.keys(compileOpts).length > 0) {
          payload.compile = compileOpts;
        }

        const executeOpts = readIsolateOptions("execute_");
        const mergedExecute = { ...defaults.executeDefaults, ...executeOpts };
        if (Object.keys(mergedExecute).length > 0) {
          payload.execute = mergedExecute;
        }

        const judgeLangAdv = document.getElementById("judge_lang_adv").value.trim();
        const judgeSourceAdv = document.getElementById("judge_source_adv").value;
        const judgeFaultRaw = document.getElementById("judge_fault_exitcode").value;
        const judgeCompileOpts = readIsolateOptions("judge_compile_");

        if (judgeLangAdv) {
          payload.judge_lang = judgeLangAdv;
        }
        if (judgeSourceAdv.trim()) {
          payload.judge_source = judgeSourceAdv;
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

        const tests = collectTests(true);
        if (tests.length > 0) {
          payload.tests = tests;
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

    addTestBtn.addEventListener("click", () => {
      testsList.appendChild(createTestCard(testsList.querySelectorAll('.test-card').length));
      renumberTests();
      updateTestsAdvancedVisibility();
      refreshPreview();
    });

    removeTestBtn.addEventListener("click", () => {
      const cards = testsList.querySelectorAll('.test-card');
      if (cards.length <= 1) {
        return;
      }
      cards[cards.length - 1].remove();
      renumberTests();
      refreshPreview();
    });

    testsBuilderWrap.addEventListener("input", () => {
      updateJudgeOptionVisibility();
      refreshPreview();
    });
    testsBuilderWrap.addEventListener("change", () => {
      updateJudgeOptionVisibility();
      refreshPreview();
    });

    modeEl.addEventListener("change", () => {
      setMode(modeEl.value);
      refreshPreview();
    });

    ["judge_lang_adv", "judge_source_adv"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener("input", () => {
          updateJudgeOptionVisibility();
          refreshPreview();
        });
      }
    });

    testsList.appendChild(createTestCard(0));
    renumberTests();
    setMode(modeEl.value);

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