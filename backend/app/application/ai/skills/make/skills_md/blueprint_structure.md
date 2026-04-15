# Make.com Blueprint Structure (verified April 2026)

A Make.com scenario blueprint is a JSON document with three top-level keys:

```
{
  "name": "<scenario name>",
  "flow": [ ... modules in execution order ... ],
  "metadata": { ... scenario-level settings ... }
}
```

## Top-level fields

- `name` (string, required) — human-readable scenario name
- `flow` (array, required) — ordered list of modules. The FIRST module is the trigger
- `metadata` (object, required) — scenario configuration block

## Module object shape

Every module in `flow` (and in `routes[].flow`) has this shape:

```
{
  "id": <integer>,                    // unique per scenario, 1..N
  "module": "<appName>:<operation>",  // e.g. "google-sheets:watchUpdatedCells"
  "version": <integer>,               // module version, e.g. 2
  "parameters": { ... },              // connection + static config (connection IDs go here)
  "mapper": { ... },                  // per-run field mappings (uses {{N.field}} expressions)
  "metadata": {
    "designer": { "x": <int>, "y": <int> }  // canvas position
  }
}
```

Optional per-module fields:
- `filter` — conditional execution. Shape: `{"name": "<label>", "conditions": [[{"a": "{{N.f}}", "b": "value", "o": "text:equal"}]]}` (outer array = OR groups, inner array = AND conditions)
- `routes` — present ONLY on router modules (`builtin:BasicRouter`). Each route is `{"flow": [...nested modules...]}`
- `mapper` can be `null` for modules with no per-run mappings (like routers)

## Router module

Router is a built-in module that fan-outs execution. Its shape:

```
{
  "id": 7,
  "module": "builtin:BasicRouter",
  "version": 1,
  "mapper": null,
  "metadata": { "designer": { "x": 300, "y": 450 } },
  "routes": [
    { "flow": [ {module1}, {module2}, ... ] },
    { "flow": [ {module3}, ... ] }
  ]
}
```

Routers can be nested inside routes of other routers.

## metadata block (scenario settings)

```
{
  "instant": <bool>,        // true if triggered by webhook, false if scheduled
  "version": 1,             // blueprint format version (always 1 today)
  "scenario": {
    "roundtrips": 1,
    "maxErrors": 3,
    "autoCommit": true,
    "autoCommitTriggerLast": true,
    "sequential": false,
    "confidential": false,
    "dataloss": false,
    "dlq": false,
    "freshVariables": false
  },
  "designer": { "orphans": [] },
  "zone": "us1.make.com"   // or eu1.make.com / eu2.make.com
}
```

## Expression syntax in `mapper` values

- Reference another module's output: `{{<moduleId>.<fieldName>}}` — e.g. `{{14.rowValues[].`4`}}`
- Formatted date: `{{formatDate(14.startDate; "MM/DD/YYYY"; "New_York")}}`
- Backtick-quoted column indices for Google Sheets: `{{14.rowValues[].`0`}}`
- Functions use semicolons between args, not commas: `{{if(14.flag = true; "✅"; "❌")}}`

## Connection placeholder

For any module that needs an account connection, use a placeholder integer in `parameters.__IMTCONN__` (e.g. `1`). Users will rewire this to a real connection on import.
For webhook triggers, use `parameters.__IMTHOOK__` with a placeholder integer.
