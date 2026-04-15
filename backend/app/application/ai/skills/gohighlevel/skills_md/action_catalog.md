# GoHighLevel Workflow Actions (verified April 2026)

Use these EXACT action names. The `action_name` field in the build spec must match one of these strings.

## Contact
- Create Contact — Adds a new contact to the system
- Find Contact — Locates a contact based on provided data
- Update Contact Field — Modifies a specific field on a contact
- Add Contact Tag — Adds a tag to a contact
- Remove Contact Tag — Removes a tag from a contact
- Assign to User — Assigns a contact to a user
- Remove Assigned User — Removes the assigned user from a contact
- Edit Conversation — Marks, archives, or unarchives a conversation
- Disable/Enable DND — Toggles Do Not Disturb for a contact
- Add Note — Adds a custom note to a contact
- Add Task — Creates a task related to a contact
- Copy Contact — Duplicates a contact into another sub-account
- Delete Contact — Removes a contact from the system
- Modify Contact Engagement Score — Adjusts a contact's engagement score
- Add/Remove Contact Followers — Adds or removes contact followers

## Communication
- Send Email — Sends an email to the contact
- Send SMS — Sends an SMS to the contact
- Send Slack Message — Sends a message via Slack (if integrated)
- Call — Makes a phone call and rings a user
- Messenger — Sends a Facebook message
- Instagram DM — Sends an Instagram Direct Message
- Manual Action — Prompts a user to perform a manual action
- GMB Messaging — Responds to Google My Business messages
- Send Internal Notification — Notifies assigned users
- Send Review Request — Sends a review request
- Conversation AI — Manages inbound conversations with AI
- WhatsApp — Sends WhatsApp messages
- Reply in Comments — Replies to Facebook or Instagram comments
- Send Live Chat Message — Responds to live chat

## Send Data
- Webhook/Custom Webhook — Sends data from HighLevel to external applications
- Google Sheets — Manages data in Google Sheets

## Internal Tools (control flow — these are step_type variants, not "action" steps)
- If Else — Creates branches based on conditions (use step_type: "if_else")
- Wait Step — Delays the workflow (use step_type: "wait")
- Goal Event — Directs contacts to a specific goal (use step_type: "goal")
- Split — Conducts a split test (use as action with action_name "Split")
- Update Custom Value — Updates custom values dynamically
- Go To — Directs contact to another workflow (use step_type: "go_to")
- Remove from Workflow — Removes contact from a workflow
- Drip Mode — Drips contacts through the workflow in batch sizes
- Text Formatter — Formats text
- Custom Code — Executes custom code

## AI
- AI Prompt — Generates AI response from a prompt
- Eliza AI Appointment Booking — Automates appointment booking via AI
- Send to Eliza Agent Platform — Sends contact to Eliza Agent

## Appointments
- Update Appointment Status — Updates status (rescheduled, no-show, completed)
- Generate One Time Booking Link — Generates a one-time booking link

## Opportunities
- Create/Update Opportunity — Creates or updates an opportunity
- Remove Opportunity — Removes an opportunity from pipelines

## Payments
- Stripe One-Time Charge — Charges a one-time fee via Stripe
- Send Invoice — Sends a HighLevel invoice
- Send Documents and Contracts — Sends a document or contract

## Marketing
- Add to Google Analytics — Adds contact data to Google Analytics
- Add to Google AdWords — Adds contact to Google AdWords
- Add to Custom Audience (Facebook) — Adds to Facebook custom audience
- Remove from Custom Audience (Facebook) — Removes from Facebook custom audience
- Facebook Conversion API — Sends conversion data to Facebook

## Step type mapping cheat sheet

When writing a step in the build spec, use these `step_type` values:

| User intent | step_type | action_name | Notes |
|---|---|---|---|
| Send a message / update a field / create record | `action` | exact name from above | Most common case |
| Pause before next step | `wait` | (omit) | Put duration in `wait_duration` |
| Branch on a condition | `if_else` | (omit) | Put description in `branch_condition`, set `if_true_next_step` and `if_false_next_step` |
| Jump to another workflow | `go_to` | (omit) | Put target workflow name in `configuration.target_workflow` |
| Mark a conversion goal | `goal` | (omit) | Put goal label in `configuration.goal_name` |
| End this branch | `end` | (omit) | No configuration needed |

## Rule when unsure
If the user describes an action that doesn't match any name above, pick the closest match and add a `notes` field explaining the approximation.
