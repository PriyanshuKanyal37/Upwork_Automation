# AI Customer Support Chatbot + Admin Dashboard for Everbright SaaS

## 🎯 The problem you're solving
- Your support team drowns in repetitive ticket questions that your 500-doc knowledge base already answers
- Customers wait hours overnight for answers your docs could give in seconds
- You need humans on the hard cases, not the FAQ ones — and no visibility into which is which today

---

## 🧭 How I'll solve it
- **Knowledge ingestion** — chunk your 500-doc knowledge base into ~2000 semantic passages, embed with OpenAI `text-embedding-3-large`, and index in Pinecone for low-latency retrieval
- **RAG chatbot API** — FastAPI endpoint that retrieves the top-5 passages per query, prompts GPT-4o with explicit citation requirements, and returns the answer plus source links so customers can verify
- **Confidence scoring** — every answer gets a score based on retrieval similarity and model logprobs; anything under threshold auto-escalates to Intercom instead of guessing
- **Admin review loop** — React dashboard where your team flags wrong answers in one click, which writes corrections back into a retraining set that re-embeds nightly
- **Intercom handoff** — seamless escalation to human inbox with full conversation context attached, so the agent never has to ask "what did the bot already tell you?"
- **Deployment** — Dockerized for your existing infrastructure, env-based config, one-command rollback, full handover docs

---

## 📦 What you'll end up with
| Deliverable | Why it matters |
|---|---|
| **Chatbot API (FastAPI)** | Auth-protected endpoint your frontend team can call from anywhere |
| **Embeddable widget (Next.js)** | Drop-in chat bubble for your site, themeable to match your brand |
| **Admin dashboard (React)** | Your team reviews and corrects answers without engineering help |
| **Intercom integration** | Hard questions reach a human with full context, no re-explaining |
| **Deployment + handover docs** | Your team can run, debug, and extend the system after handover |

---

## 🛡 How I'll handle the tricky parts
- **Hallucinations** — the retrieval prompt forces the model to quote source passages; answers without a citation are suppressed and auto-escalated to a human
- **Knowledge drift** — a nightly re-embedding job picks up new docs, deleted docs, and flagged corrections from the admin dashboard automatically
- **Edge-case questions** — anything below the confidence threshold (measured on 50 of your real past tickets before launch) goes straight to Intercom with full context
- **Rate limits and cost spikes** — per-user query limits, OpenAI cost monitoring, and a hard daily budget cap so a runaway loop can't drain your API budget

---

## ⚡ Why me
- Shipped 5 production AI chatbots in the last 12 months — all OpenAI + Pinecone RAG, all with human-handoff flows
- Full-stack across the model, API, and React layers — no handoffs between freelancers, no waiting on other contractors
- Direct Slack line with you during the build, daily short Loom updates so you always know where we stand

> Last similar project shipped 2 days ahead of schedule with 87% answer accuracy on a held-out ticket set.

---

## 👉 Timeline & next step
Rough duration: ~3 weeks from kickoff to handover. Accept this proposal and I'll send a 20-minute scoping call invite for tomorrow to lock the knowledge-base access and your Intercom API credentials.
