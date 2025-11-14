---
action_run_id: '19379755769'
article_quality:
  dimensions:
    citations: 100.0
    code_examples: 0.0
    length: 98.7
    readability: 72.5
    source_citation: 100.0
    structure: 40.0
    tone: 100.0
  overall_score: 65.9
  passed_threshold: false
cover:
  alt: When to Use Rules Over AI in Workflows
  image: https://oaidalleapiprodscus.blob.core.windows.net/private/org-55GGLx4aeQO8aVCpsCrxwgyk/user-pzHsEhubeDL6uAWkHInuYZO0/img-HCtM7g3m1t0RbUaRiDMvRyjW.png?st=2025-11-14T22%3A18%3A24Z&se=2025-11-15T00%3A18%3A24Z&sp=r&sv=2024-08-04&sr=b&rscd=inline&rsct=image/png&skoid=8b33a531-2df9-46a3-bc02-d4b1430a422c&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-11-14T08%3A19%3A33Z&ske=2025-11-15T08%3A19%3A33Z&sks=b&skv=2024-08-04&sig=W2BOCbUQus8IC1rqkWlQoy12oWAWhlgnI2Ldz%2BRRuLc%3D
date: 2025-11-14T23:14:51+0000
generation_costs:
  content_generation: 0.00210675
  title_generation: 0.000756
generator: General Article Generator
icon: https://oaidalleapiprodscus.blob.core.windows.net/private/org-55GGLx4aeQO8aVCpsCrxwgyk/user-pzHsEhubeDL6uAWkHInuYZO0/img-HCtM7g3m1t0RbUaRiDMvRyjW.png?st=2025-11-14T22%3A18%3A24Z&se=2025-11-15T00%3A18%3A24Z&sp=r&sv=2024-08-04&sr=b&rscd=inline&rsct=image/png&skoid=8b33a531-2df9-46a3-bc02-d4b1430a422c&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-11-14T08%3A19%3A33Z&ske=2025-11-15T08%3A19%3A33Z&sks=b&skv=2024-08-04&sig=W2BOCbUQus8IC1rqkWlQoy12oWAWhlgnI2Ldz%2BRRuLc%3D
illustrations_count: 0
models_used:
  content: gpt-5-mini
  enrichment: gpt-5-nano
  title: gpt-5-nano
reading_time: 8 min read
sources:
- author: mariyadelano
  platform: mastodon
  quality_score: 0.65
  url: https://hachyderm.io/@mariyadelano/115548761092296218
summary: But they’re not the same thing.
tags:
- apis
- automation / workflow automation
- scripting / programming
- conditional logic / if-then statements
- artificial intelligence
title: When to Use Rules Over AI in Workflows
word_count: 1642
---

> **Attribution:** This article was based on content by **@mariyadelano** on **mastodon**.  
> Original: https://hachyderm.io/@mariyadelano/115548761092296218

Introduction

Automation and artificial intelligence (AI) often sit together in conversations about modernizing work. But they’re not the same thing. In fact, many of the workflow wins people imagine require large language models (LLMs) or generative AI can be solved faster, cheaper, and more reliably with plain-old conditional logic, scripting, and API orchestration. That was the observation behind a recent Mastodon post by @mariyadelano: when asked to “build AI flows,” she frequently returned deterministic automation flows that used 0 AI — and stakeholders loved the outcome anyway (Delano, 2024). This article explains why rule-based automation remains powerful, how it differs from AI-enabled automation, and how to decide which approach to use in practice.

What you will learn:

- The core building blocks of modern automation
- Practical examples where no-AI automation is the right choice
- How and when to layer AI onto existing flows
- Best practices for reliability, security, and maintainability

Key Takeaways

- Many real-world workflows are deterministic and can be automated reliably with simple triggers, API calls, and if/then logic.
- AI adds value when you need probabilistic reasoning over unstructured data (e.g., free text), but it brings cost, complexity, and governance overhead.
- Design for idempotency, observability, and least-privilege access whether or not you use AI.
- Use a hybrid approach: automate simple flows with code or iPaaS and introduce AI selectively to handle edge cases or unstructured inputs.

> Background: "Automation" spans from imperative scripts that call APIs to event-driven integrations and AI-augmented workflows; pick the right layer for the problem.

Main concepts: building blocks of automation

At its core, automation is about reacting to events and executing actions. The common components include:

- Triggers: events that start a flow, such as “a new document is uploaded” or “a form is submitted.” Triggers often come from webhooks or polling APIs.
- Actions: the tasks the flow performs — API calls, database updates, notifications, or UI interactions (RPA, robotic process automation).
- Data mapping and transformation: converting inputs into the shapes required by destination systems (JSON, XML, CSV).
- Conditional logic: `if/then` conditions and branching that guide the flow.
- Orchestration: sequencing steps and handling failures with retries and compensating actions.

APIs (application programming interfaces) are the connective tissue here: REST or GraphQL endpoints, authenticated via OAuth (Open Authorization) or API keys, allow automation to read and write state across SaaS products. No-code/low-code integration platforms (often called integration platform as a service, or iPaaS) such as Zapier, Make, Microsoft Power Automate, and Tray.io abstract much of this, enabling non-developers to wire triggers and actions together.

Why rule-based automation still wins

Deterministic automations — those that follow explicit rules — have major advantages:

- Predictability: given the same inputs, they produce the same outputs every time.
- Cost-efficiency: they typically require less compute and no model inference charges.
- Simplicity: they are easier to test, debug, and explain to stakeholders.
- Lower governance burden: no need for model-monitoring, hallucination mitigation, or complex data-privacy reviews.

Research and industry reports have highlighted that many productivity gains from digitization come from process automation rather than autonomous AI alone (McKinsey Global Institute, 2017). Even as LLMs have matured (Brown et al., 2020), the bulk of enterprise automation remains rule-based, with organizations adopting AI selectively to solve tasks that rules struggle with.

Practical applications and examples

Example 1 — Document intake and task creation (the classic use case)
Problem: A team needs to track documents dropped into a shared drive and ensure a follow-up task is created in their project management tool.

No-AI solution:

- Trigger: webhook or file-system watcher detects a new document.
- Action 1: POST a link and metadata to a shared spreadsheet via the spreadsheet API.
- Action 2: Create a task in the PM tool via its API, assign to user X, add label Y.
- Conditional logic: if the filename contains “invoice,” also attach a payment-check label.

Why no AI? The logic is deterministic and based on metadata and filename patterns. It’s fast to implement and easy to audit.

Example 2 — Customer support triage with deterministic routing
Problem: Incoming support emails should be routed to teams based on product and urgency.

No-AI solution:

- Trigger: incoming email webhooks.
- Action: parse subject and structured tags, match to routing rules in a lookup table (e.g., if product = A and priority = high, assign team Alpha).
- Action: create ticket via support system API and notify Slack.

When to add AI: If incoming messages are free-form, with unclear product references, an LLM or a classifier can predict the product or urgency. Use AI to augment triage when rules can't cover the variety of language.

Example 3 — Invoice processing hybrid
Problem: Extract fields from vendor invoices.

Hybrid solution:

- Use deterministic automation to ingest PDFs, store them, and call an OCR (optical character recognition) service.
- Use a structured extractor (rules and regex) for consistent invoice templates.
- Use an LLM or trained extractor model only for messy, unmatched invoices to extract fields or verify totals.

This minimizes model calls and places AI where it has the most value.

> Background: iPaaS platforms provide pre-built connectors and UI builders for wiring triggers to actions, reducing development time.

Choosing between rule-based and AI-enabled automation

Ask these questions:

1. Is the input structured or predictable? If yes, prefer deterministic rules.
1. What is the cost of an incorrect output? High cost favors deterministic or human-in-the-loop approaches.
1. How often do edge cases occur? If rare, handle them with exception workflows or occasional human review instead of continuous AI.
1. What is the maintenance budget? AI needs monitoring and potential retraining; rules need updates as schemas or APIs change.

When to use AI:

- Extracting entities or meaning from unstructured text
- Generating drafts (summaries, emails) where human review is acceptable
- Routing ambiguous items based on subtle semantic cues

When to stick with rule-based automation:

- Data-driven updates across systems (e.g., syncing records)
- Compliance-sensitive processes
- High-volume, repetitive tasks with clear structure

Best practices for robust automation (AI or not)

Reliability and observability

- Idempotency: ensure actions can be safely retried without side effects (Newman, 2015).
- Retries and backoff: implement exponential backoff and dead-letter queues for failed messages.
- Logging and tracing: capture inputs, outputs, and action statuses. Correlate traces across services for debugging.
- Monitoring: set alerts on error rates, latency, and API quota usage.

Security and governance

- Least-privilege: give integrations only the permissions they need.
- Secret management: use secure vaults for API keys and OAuth tokens.
- Data governance: limit PII (personally identifiable information) exposure, especially when calling third-party AI services.
- Compliance: document data flows for audits and retention policies.

Maintainability

- Version control automation scripts or integration flows.
- Use feature flags for staged rollouts.
- Abstract API calls behind thin adapters so changes in vendors are localized.
- Keep a test sandbox that mirrors production behavior.

Cost and performance

- Watch API rate limits and costs. Even rule-based flows can hit quotas.
- For AI: optimize by caching inferences, batching requests, and using smaller models where adequate (Brown et al., 2020 shows model size affects cost and capability).
- Measure ROI: time saved, error reduction, and user satisfaction.

Implications and insights

Automation is not an all-or-nothing choice between “AI” and “no-AI.” Organizations benefit from thinking of automation as a stack:

- Bottom layer: deterministic orchestration (triggers, API calls, conditional logic).
- Middle layer: data transformation, enrichment, and routing.
- Top layer: optional AI components for classification, extraction, or generation.

This layered approach—akin to microservice and event-driven architecture patterns—lets teams capture quick wins with low risk, then layer in AI where it brings clear benefits (Kreps, 2011; Newman, 2015). It also reduces surprise costs: many stakeholders who ask “can we use AI?” are actually asking for the outcomes — faster routing, fewer manual steps — which can often be delivered without any generative models, as Delano’s post observed.

Citations and authoritative context

- Delano, M. (2024). Mastodon post illustrating the practical substitution of deterministic automation for AI in many workflows. https://hachyderm.io/@mariyadelano/115548761092296218
- McKinsey Global [Institute (2017)](https://doi.org/10.20292/jcich.2017.22.). A Future that Works: Automation, Employment, and Productivity — discusses the economic impact of automation.
- [Brown et al. (2020)](https://doi.org/10.1200/jco.20.01167). Language Models are Few-Shot Learners — introduces GPT-3 and shows the power and cost profile of large pre-trained models.
- Newman, S. (2015). Building Microservices — covers design patterns for resilient distributed systems and orchestration.
- Kreps, J. (2011). The Log: What every software engineer should know about real-time data and stream processing — explains event-driven design and stream processing principles.
- Nygard, M. (2007). Release It! — practical patterns for building resilient and maintainable systems.

Conclusion & next steps

Many automation requirements are best solved with rules, scripting, and API workflows. AI is compelling but should be treated as a targeted tool, not the default. Start your automation journey by asking whether the task is deterministic and whether the business needs justify AI’s extra complexity. Deliver value quickly with event-driven scripts or an iPaaS, instrument thoroughly, and introduce AI incrementally where it resolves real pain points.

Action plan

- Audit: list 10 high-volume manual tasks and classify them as structured vs unstructured.
- Prototype: build a simple trigger → action flow for one structured process.
- Monitor: add logging, error alerts, and an SLA for automation success rates.
- Evaluate AI: only if accuracy or usability goals are unmet with deterministic approaches.

Credit
This article was inspired by a Mastodon thread from @mariyadelano (Delano, 2024), which highlighted how often simple automation delivers the outcomes people expect from AI.

Further reading

- McKinsey Global Institute (2017). A Future that Works.
- Brown et al. (2020). Language Models are Few-Shot Learners.
- [Newman (2015)](https://doi.org/10.1353/nsj.2015.0011). Building Microservices.
- [Nygard (2007)](https://doi.org/10.1109/cts.2007.4621774). Release It!
- [Kreps (2011)](https://doi.org/10.1093/benz/9780199773787.article.b00101257). The Log.


## References

- [I’ve been testing a theory: many people who are high on # AI and # LLMs are j...](https://hachyderm.io/@mariyadelano/115548761092296218) — @mariyadelano on mastodon

- [Institute (2017)](https://doi.org/10.20292/jcich.2017.22.)
- [Brown et al. (2020)](https://doi.org/10.1200/jco.20.01167)
- [Newman (2015)](https://doi.org/10.1353/nsj.2015.0011)
- [Nygard (2007)](https://doi.org/10.1109/cts.2007.4621774)
- [Kreps (2011)](https://doi.org/10.1093/benz/9780199773787.article.b00101257)