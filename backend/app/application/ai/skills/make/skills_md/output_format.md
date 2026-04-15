# Flat Output Format (for post-processing into nested blueprint)

You MUST output a FLAT module list, not a nested blueprint. Our Python post-processor converts the flat list to the nested Make.com blueprint structure.

This works around the fact that structured outputs cannot express recursive schemas.

## Output shape

```
{
  "name": "<scenario name>",
  "zone": "us1.make.com",
  "instant": <bool>,
  "modules": [
    {
      "id": <int>,
      "parent_id": <int|null>,       // null = top-level module, int = inside a route of that router
      "route_index": <int|null>,     // null for top-level or router; int for modules inside route N of parent router
      "module": "<appName:operation>",
      "version": <int>,
      "mapper": { ... } | null,
      "parameters": { ... },
      "filter": { ... } | null,
      "position_x": <int>,
      "position_y": <int>,
      "is_router": <bool>,           // true if this is a builtin:BasicRouter
      "route_count": <int|null>      // how many routes the router has (null if not a router)
    },
    ...
  ]
}
```

## How parent_id + route_index work

- Top-level modules (directly in the main `flow` array): `parent_id = null`, `route_index = null`
- A router at the top level: `parent_id = null`, `route_index = null`, `is_router = true`, `route_count = 2` (or however many routes)
- A module inside route 0 of that router: `parent_id = <router id>`, `route_index = 0`
- A module inside route 1 of that router: `parent_id = <router id>`, `route_index = 1`
- A router nested inside route 0 of another router: `parent_id = <outer router id>`, `route_index = 0`, `is_router = true`

## Example (flat representation of a scheduled sheet-to-email flow with a router)

```
{
  "name": "Daily Report Router",
  "zone": "us1.make.com",
  "instant": false,
  "modules": [
    {"id": 1, "parent_id": null, "route_index": null, "module": "google-sheets:watchRows", "version": 2, "mapper": {}, "parameters": {"__IMTCONN__": 1}, "filter": null, "position_x": 0, "position_y": 0, "is_router": false, "route_count": null},
    {"id": 2, "parent_id": null, "route_index": null, "module": "builtin:BasicRouter", "version": 1, "mapper": null, "parameters": {}, "filter": null, "position_x": 300, "position_y": 0, "is_router": true, "route_count": 2},
    {"id": 3, "parent_id": 2, "route_index": 0, "module": "gmail:ActionSendEmail", "version": 1, "mapper": {"to": ["{{1.email}}"], "subject": "Daily Report", "content": "Hi {{1.name}}"}, "parameters": {"__IMTCONN__": 1}, "filter": {"name": "high priority", "conditions": [[{"a": "{{1.priority}}", "b": "high", "o": "text:equal"}]]}, "position_x": 600, "position_y": -150, "is_router": false, "route_count": null},
    {"id": 4, "parent_id": 2, "route_index": 1, "module": "slack:CreateMessage", "version": 4, "mapper": {"channel": "C123", "text": "New row: {{1.name}}"}, "parameters": {"__IMTCONN__": 1}, "filter": null, "position_x": 600, "position_y": 150, "is_router": false, "route_count": null}
  ]
}
```

The Python post-processor will convert this into a nested `flow` array where the router module has its `routes[0].flow = [module 3]` and `routes[1].flow = [module 4]`.

## Hard rules

1. Module `id`s are unique positive integers. Start at 1, increase monotonically.
2. A module's `parent_id` must reference a router that appears EARLIER in the list (lower id).
3. If `is_router` is true, `route_count` must be `>= 1`; every route index from 0 to `route_count - 1` must have at least one child module.
4. The first module in `modules` (id 1) must be a trigger — it must have `parent_id: null`.
5. `mapper` is `null` for routers; for other modules it's an object (can be empty `{}` if no fields mapped).
6. Position coordinates: trigger at (0, 0); each downstream top-level module at x += 300; router children at parent_x + 300 and y offset per route_index.
7. Every module that needs a connection: put `parameters.__IMTCONN__ = 1` (placeholder). Webhook triggers: `parameters.__IMTHOOK__ = 1`.
8. Expressions in `mapper` values use `{{<moduleId>.<field>}}` to reference earlier modules' output.
