# Camisole HTTP API

This document describes the HTTP endpoints exposed by Camisole and the request payloads they accept.

Camisole accepts and returns either JSON (`application/json`) or MessagePack (`application/msgpack`). The response format is selected from the request `Accept` header. The request body format is selected from `Content-Type`.

## Overview

| Endpoint | Method | Description |
| --- | --- | --- |
| `/run` | `POST` | Compile and execute code, optionally with tests or interactive judge mode |
| `/languages` | `GET`, `POST`, `*` | List enabled languages and their binaries |
| `/system` | `GET`, `POST`, `*` | Return host system information |
| `/test` | `GET`, `POST`, `*` | Run the built-in reference test suite for all loaded languages |
| `/` | `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `*` | Return a welcome message |

All successful responses include:

```json
{
  "success": true
}
```

All error responses include:

```json
{
  "success": false,
  "error": "..."
}
```

## Content Types

Camisole understands the following content types:

- `application/json`
- `application/msgpack`

If the request body cannot be decoded, the server returns a `400 Bad Request` response.

If the server cannot encode the response in a format accepted by the client, it returns a `406 Not Acceptable` response.

JSON is the default request format when `Content-Type` is missing or unsupported.

## `POST /run`

Compile and execute source code.

### Request body

The request body must be an object with the following fields.

### Required fields

- `lang` `string`: language name, case-insensitive
- `source` `string | bytes`: program source code

### Optional fields

- `all_fatal` `boolean`: stop at the first failing test
- `compile` `object`: isolate options applied during compilation
- `execute` `object`: isolate options applied during execution
- `tests` `array`: list of tests to run
- `judge_source` `string | bytes`: source code of the judge program for interactive mode
- `judge_lang` `string`: language of the judge program for interactive mode
- `judge_compile` `object`: isolate options applied during judge compilation
- `judge_fault_exitcode` `integer`: exit code that should be interpreted as `FAULT`
- `stdin_user` `string | bytes`: initial input injected into the user process in interactive mode
- `stdin_judge` `string | bytes`: initial input injected into the judge process in interactive mode

### Isolate options

The following isolate options are accepted in `compile`, `execute`, and per-test execution overrides:

- `extra-time` `number`
- `fsize` `integer`
- `mem` `integer`
- `processes` `integer`
- `quota` `string`
- `stack` `integer`
- `time` `number`
- `virt-mem` `integer`
- `wall-time` `number`

In addition, `execute` accepts interactive stdin defaults:

- `stdin` `string | bytes`: backward-compatible alias for user initial stdin in interactive mode
- `stdin_user` `string | bytes`: default initial stdin for user process
- `stdin_judge` `string | bytes`: default initial stdin for judge process

### Test object fields

Each element of `tests` can contain:

- `name` `string`: test name, defaults to `test000`, `test001`, and so on
- `stdin` `string | bytes`: standard input for the test
- `stdin_user` `string | bytes`: initial input injected into user process for this test
- `stdin_judge` `string | bytes`: initial input injected into judge process for this test
- `fatal` `boolean`: stop running later tests if this one fails
- `judge` `boolean`: enable judge mode for this test
- `judge_fault_exitcode` `integer`: per-test override for the judge fault exit code
- `firewall_rules` `object`: I/O filtering rules for interactive mode
- `user_execution` `object`: isolate options applied only to the user program
- `judge_execution` `object`: isolate options applied only to the judge program
- any isolate option listed above, used as a backward-compatible shorthand for execution limits

### Firewall rules

`firewall_rules` accepts the following fields:

- `allowed_chars` `string`: regular expression for allowed characters
- `max_line_length` `integer`: maximum bytes per line
- `max_total_bytes` `integer`: maximum bytes the user may send to the judge
- `format_rules` `array[string]`: custom validator names
- `violation_action` `string`: `STOP` or `WARN`

### Standard mode response

When the request is not interactive judge mode, the response contains:

- `compile`: compilation report, when compilation happens
- `tests`: array of execution reports

Each compile or test report typically includes:

- `stdout`
- `stderr`
- `exitcode`
- `meta`

The `meta` object contains execution details such as:

- `status`
- `time`
- `wall-time`
- `cg-mem`
- `max-rss`
- `csw-voluntary`
- `csw-forced`
- `killed`
- `exitsig`
- `exitsig-message`
- `message`

### Interactive judge mode response

If both `judge_source` and `judge_lang` are provided, Camisole switches to interactive mode and returns verdict-oriented fields in each test result.

Common fields include:

- `verdict`: `PASS`, `FAULT`, `JUDGE_RUNTIME_ERROR`, `USER_RUNTIME_ERROR`, `JUDGE_TIMEOUT`, `USER_TIMEOUT`, `FIREWALL_VIOLATION`, `JUDGE_CRASHED`, `USER_CRASHED`, `RESOURCE_LIMIT_EXCEEDED`, or `PROXY_COMMUNICATION_ERROR`
- `user_exit_code`
- `judge_exit_code`
- `user_signal`
- `judge_signal`
- `firewall_violation`
- `judge_output`
- `user_stderr`
- `judge_stderr`
- `total_user_bytes_sent`
- `total_judge_bytes_sent`
- `io_transcript`
- `resource_limit_exceeded`
- `error_message`

If the judge language defines a custom fault exit code, a matching judge exit code is reported as `FAULT`.

### Example request

```json
{
  "lang": "python",
  "source": "print(42)",
  "tests": [
    {
      "name": "sample",
      "stdin": ""
    }
  ]
}
```

### Example response

```json
{
  "success": true,
  "compile": {
    "exitcode": 0,
    "meta": {
      "status": "OK"
    },
    "stderr": "",
    "stdout": ""
  },
  "tests": [
    {
      "name": "sample",
      "exitcode": 0,
      "meta": {
        "status": "OK"
      },
      "stderr": "",
      "stdout": "42\n"
    }
  ]
}
```

### Common errors

- `malformed payload: ...`: the request body does not match the expected schema
- `malformed application/json`: the body could not be decoded as JSON
- `malformed application/msgpack`: the body could not be decoded as MessagePack
- `Incorrect language ...`: the requested language is not registered
- `No executer configured for language ...`: the language exists but cannot be executed
- `use 'Accept: application/msgpack' to be able to receive binary payloads`: JSON was requested but the response contains binary data

## `GET` or `POST /languages`

Return the list of loaded languages.

### Response body

```json
{
  "success": true,
  "languages": {
    "python": {
      "name": "Python",
      "programs": {
        "python3": {
          "version": "3.12.2",
          "opts": ["-S"]
        }
      }
    }
  }
}
```

Each language entry contains:

- `name`: display name
- `programs`: mapping of binary names to version and command-line options

## `GET` or `POST /system`

Return information about the host where Camisole is running.

### Response body

```json
{
  "success": true,
  "system": {
    "arch": "x86_64",
    "byte_order": "little",
    "cpu_count": 1,
    "cpu_mhz": 2494.214,
    "cpu_name": "Intel(R) Core(TM) ...",
    "kernel": "Linux",
    "kernel_release": "...",
    "kernel_version": "...",
    "memory": 2102362112
  }
}
```

## `GET` or `POST /test`

Run the built-in reference tests for all loaded languages.

### Request body

Optional field:

- `exclude` `array[string]`: language names to skip

### Response body

```json
{
  "success": true,
  "results": {
    "python": {
      "success": true,
      "raw": { }
    }
  }
}
```

Each language entry contains:

- `success`: whether the reference program produced the expected output
- `raw`: the full raw execution result returned by the language runner

## `GET /`

Return a small welcome message.

### Response body

Plain text:

```text
Welcome to Camisole. Use the /run endpoint to run some code!
```

## Notes

- If the request body is empty, Camisole treats it as an empty object.
- For binary source code or binary outputs, prefer MessagePack and set `Accept: application/msgpack`.
- If `Accept` allows both JSON and MessagePack, Camisole will choose the best available format automatically.
