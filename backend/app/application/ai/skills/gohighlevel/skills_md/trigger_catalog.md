# GoHighLevel Workflow Triggers (verified April 2026)

Use these EXACT trigger names. The `type` field in the build spec must match one of these strings.

## Contact
- Birthday Reminder — Fires on contact's birthday using configured offset
- Contact Changed — Activates when specified contact fields change to defined values
- Contact Created — Triggers when new contact record is added to CRM
- Contact DND — Activates on Do Not Disturb preference changes
- Contact Tag — Triggers when tag is added to or removed from contact
- Custom Date Reminder — Fires before/on/after chosen custom date field
- Note Added — Activates when new note is added to contact
- Note Changed — Triggers when existing contact note is edited
- Task Added — Activates when task is created for contact
- Task Reminder — Triggers when task reminder time arrives
- Task Completed — Activates when contact's task is marked complete
- Contact Engagement Score — Fires when engagement score meets defined rule

## Events
- Inbound Webhook — Fires when data is received at the workflow's webhook URL
- Scheduler — Fires on time-based schedule without requiring contact
- Call Details — Activates when call log matches selected details or outcomes
- Email Events — Fires on email delivered, opened, clicked, bounced, spam, or unsubscribe
- Customer Replied — Triggers when contact replies on connected channel
- Conversation AI Trigger — Activates when configured Conversation AI event occurs
- Custom Trigger — Fires from a custom event you define
- Form Submitted — Activates when selected HighLevel form is submitted
- Survey Submitted — Triggers when selected survey is submitted
- Trigger Link Clicked — Activates when contact clicks defined trigger link
- Facebook Lead Form Submitted — Fires when a Facebook Lead Ad form submission is received
- TikTok Form Submitted — Triggers when TikTok lead form is submitted
- Video Tracking — Activates when viewer reaches chosen video percentage
- Number Validation — Fires based on phone number validation result
- Messaging Error – SMS — Fires when outbound SMS returns specific error
- LinkedIn Lead Form Submitted — Fires when a LinkedIn Lead Gen form submission is received
- Funnel/Website PageView — Activates when contact views specified page/URL or UTM
- Quiz Submitted — Triggers when selected quiz is submitted
- New Review Received — Fires when a new review arrives in Reviews/Reputation
- Google Lead Form Submitted — Fires when a Google Ads lead form submission is received

## Appointments
- Appointment Status — Activates on status changes (booked, rescheduled, canceled, no-show)
- Customer Booked Appointment — Fires when a customer books an appointment
- Service Booking — Triggers when booking is made using Services (v2)

## Opportunities
- Opportunity Status Changed — Fires when opportunity status changes (Open → Won/Lost)
- Opportunity Created — Fires when a new opportunity is created
- Opportunity Changed — Activates when selected opportunity fields change
- Pipeline Stage Changed — Triggers when opportunity moves to different pipeline stage
- Stale Opportunities — Fires when opportunities meet your inactivity/stale rule

## Payments
- Invoice — Activates on invoice lifecycle events (created, sent, due, paid)
- Payment Received — Fires when a payment is successfully captured
- Order Form Submission — Triggers when checkout/order form is submitted
- Order Submitted — Fires when an order is successfully submitted at checkout
- Documents & Contracts — Activates on document status events (sent, signed, declined)
- Estimates — Fires on estimate events (sent, accepted, declined)
- Subscription — Activates on subscription create, update, pause, resume, or cancel
- Refund — Fires when a refund is issued

## Ecommerce
- Shopify Order Placed — Fires when a Shopify order is placed
- Order Fulfilled — Activates when store order is fulfilled
- Product Review Submitted — Fires when a product review is submitted
- Abandoned Checkout — Fires when a checkout session is abandoned

## Courses
- New Signup — Fires when a user signs up for a course/offer
- Product Started / Product Completed — Learner begins or completes a product
- Lesson Started / Lesson Completed — Learner begins or completes a lesson
- Offer Access Granted / Offer Access Removed — Access to an offer changes

## Affiliate
- Affiliate Created — Fires when a new affiliate account is created
- New Affiliate Sales — Activates when sale is attributed to affiliate

## Rule when unsure
If the user describes a trigger that doesn't exactly match a name above, pick the closest match AND add a `notes` field on the trigger explaining the approximation so the user can verify in the UI.
