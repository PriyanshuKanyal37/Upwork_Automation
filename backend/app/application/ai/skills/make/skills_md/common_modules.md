# Common Make.com Modules (reference)

Use the EXACT `module` string and `version` below. The version number changes between Make releases; these values are verified current as of April 2026 from real exported blueprints.

## Triggers (always the first module in `flow`)

| module | version | purpose |
|---|---|---|
| `gateway:CustomWebHook` | 1 | Instant webhook trigger. Needs `parameters.hook` (placeholder int). |
| `google-sheets:watchUpdatedCells` | 2 | Watch for updated cells in a Google Sheet. |
| `google-sheets:watchRows` | 2 | Watch for new rows added. |
| `gmail:watchEmails` | 1 | Watch Gmail inbox. |
| `asana:WatchNewTasks` | 2 | Watch Asana for new tasks. |
| `airtable:watchRecords` | 3 | Watch Airtable records. |
| `scheduler` | 1 | Scheduled trigger. Use `metadata.instant: false` for scheduled scenarios. |

## HTTP

| module | version | purpose |
|---|---|---|
| `http:ActionSendData` | 3 | Make an HTTP request. `mapper` takes `url`, `method`, `headers`, `qs`, `body`. |
| `http:ActionSendDataBasicAuth` | 3 | HTTP with basic auth. |

## Google

| module | version |
|---|---|
| `google-sheets:addRow` | 2 |
| `google-sheets:updateRow` | 2 |
| `google-sheets:getRange` | 2 |
| `google-calendar:createAnEvent` | 5 |
| `google-calendar:updateAnEvent` | 5 |
| `google-docs:createADocumentFromTemplate` | 1 |
| `google-drive:uploadAFile` | 2 |

## Communication

| module | version |
|---|---|
| `slack:CreateMessage` | 4 |
| `email:ActionSendEmail` | 7 |
| `gmail:ActionSendEmail` | 1 |

## Data / CRM / Other

| module | version |
|---|---|
| `airtable:createRecord` | 3 |
| `airtable:updateRecord` | 3 |
| `notion:createADatabaseItem` | 2 |
| `hubspot:createContact` | 2 |
| `openai-gpt-3:CreateCompletion` | 1 |
| `anthropic-claude:createPromptCompletion` | 1 |

## Built-in control flow modules

| module | version | purpose |
|---|---|---|
| `builtin:BasicRouter` | 1 | Fan-out to multiple parallel routes. Has `routes: [{"flow": [...]}, ...]`. |
| `builtin:BasicFeeder` | 1 | Iterator — loop over an array. |
| `builtin:BasicAggregator` | 1 | Aggregate iterator output. |
| `builtin:SetVariable` | 1 | Set a scenario variable. |
| `util:SetVariable2` | 1 | Alternative set variable. |
| `json:ParseJSON` | 1 | Parse a JSON string into an object. |
| `json:CreateJSON` | 1 | Build a JSON string from fields. |

## Important rules

1. If the user asks for a module you don't see above, use your best guess at the `appName:operation` format and pick `version: 1`. Add a note in the flat output explaining the uncertainty.
2. Routers have `mapper: null`, not `mapper: {}`.
3. Triggers with webhooks: put the placeholder integer in `parameters.__IMTHOOK__ = 1`.
4. Any module that needs an account connection: put `parameters.__IMTCONN__ = 1`.
5. Module IDs must be unique integers starting at 1 and increasing. Don't reuse IDs across routes.
