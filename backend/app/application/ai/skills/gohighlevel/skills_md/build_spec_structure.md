# GoHighLevel Build Spec Structure (not an import file)

**IMPORTANT CONTEXT**: GoHighLevel (as of April 2026) does NOT support JSON
workflow import. There is no public API endpoint to create a full workflow
from JSON. The only official ways to transfer workflows between accounts are
Snapshots (binary sub-account templates) and manual UI recreation.

Because of this, our generator produces a **BUILD SPEC** — a structured,
human-readable description of the workflow that the user follows step by step
inside the GHL Advanced Builder. It is NOT a file the user imports.

## Build spec JSON shape

```
{
  "workflow_name": "<short human-readable name>",
  "workflow_description": "<2-3 sentences: purpose + who the contact is + goal>",
  "trigger": {
    "type": "<exact trigger name from the catalog>",
    "category": "<Contact | Events | Appointments | Opportunities | ...>",
    "configuration_notes": "<what fields to set in the trigger config panel, e.g. 'Form: Contact Us', 'Tag equals new-lead'>",
    "filter_conditions": [
      {"field": "<field name>", "operator": "equals", "value": "<value>"}
    ]
  },
  "steps": [
    {
      "step_number": 1,
      "step_type": "action | wait | if_else | goal | go_to | end",
      "name": "<short label shown in the spec>",
      "action_name": "<exact action name from the catalog, only if step_type is 'action'>",
      "action_category": "<Contact | Communication | Internal Tools | ... only if step_type is 'action'>",
      "configuration": {
        "<configuration key 1>": "<value>",
        "<configuration key 2>": "<value>"
      },
      "wait_duration": "<e.g. '1 day', '2 hours', only if step_type is 'wait'>",
      "branch_condition": "<only if step_type is 'if_else' — describe the yes/no branch point>",
      "if_true_next_step": <step_number | null>,
      "if_false_next_step": <step_number | null>,
      "notes": "<any extra guidance for the user"
    }
  ],
  "estimated_build_time_minutes": <integer>,
  "required_integrations": ["<integration 1>", "<integration 2>"],
  "required_custom_fields": ["<field 1>", "<field 2>"]
}
```

## Rules for step ordering

1. Step numbers are unique positive integers starting at 1 and increasing.
2. Non-branching steps (action, wait, goal, go_to) run sequentially by step_number.
3. A step of type `if_else` MUST specify `if_true_next_step` and `if_false_next_step` as existing step numbers (or null if the branch ends the workflow).
4. The step list is linear in the JSON, but branching is expressed via the `if_true_next_step` / `if_false_next_step` pointers on `if_else` steps. This avoids needing nested structures (which Anthropic structured outputs cannot represent).
5. An `end` step type marks a branch terminator. Every branch should eventually reach either an `end` step or the last sequential step.
6. Wait steps have `wait_duration` as a plain-English string (the user will set the exact value in the UI). Examples: "1 day", "3 hours", "15 minutes", "until 9:00 AM next business day".

## Field conventions

- `configuration` is a flat object of label → value strings. Keep it realistic but concise. The user will confirm/tweak every field in the UI.
- `filter_conditions` on the trigger use the common operators GHL supports: `equals`, `not_equals`, `contains`, `does_not_contain`, `greater_than`, `less_than`, `exists`, `does_not_exist`.
- `required_integrations` is any external connection the user must have set up (e.g. "Stripe", "Twilio", "Google Sheets", "Slack workspace").
- `required_custom_fields` is any contact-level custom field the user needs to create first for the workflow to run.
