# Our Idea – Data Minimiser (Track 1)

*Legal Hackathon – Responsible AI for Sensitive Data · 23 September 2026*

---

## Core Concept
An AI agent **understands the situation and creates rules**, but **never touches the data itself**. A **deterministic engine** applies these rules to hide or remove data. This keeps the process transparent, reproducible and privacy-safe.

## User Flow

### 1. Input Data
- Upload own data (form, flow, schema), **or**
- Use ready-made test data (for demo / graders)

### 2. Onboarding (Context Gathering)
- User describes their situation: what they work on, what the data is, how they want to protect it
- Goal: determine which **GDPR category** the data belongs to (e.g. personal vs. special-category data)
- LLM: **Apertus** (Swiss open model)
- If the agent needs more information, it **asks back**

**Form-first, chatbot second:**
- Start with a short background form; based on the answers, AI suggests the next form fields
- Structured fields, e.g.: *I need this info for [ ]*, *retention / time for approval [ ]*, *relevant GDPR clauses [ ]*
- Aim: collect everything without the chatbot; use the chatbot only for the small part that can't be figured out otherwise

### 3. Rule Generation (AI)
- Agent creates rules / filters per field (keep, make optional, remove, better explain)
- **No direct data access by the AI**

### 4. Rule Execution (Deterministic Engine)
- Engine applies the filters and hides / removes the affected data
- Option: small language model (SLM) on top for edge cases

### 5. Data Expiry
- Option for **self-expiring data**:
  - without time limit
  - with time limit

### 6. Output & Report
- Output data is GDPR-compliant
- Generated **table / PDF report** listing which fields don't comply with GDPR (and why) → handed to the person responsible for data collection, so these fields are no longer collected

## Compliance Principles
- Aligned with **GDPR** and the **Swiss Data Protection Act (revFADP / nDSG)** – made visible on the page
- If a user wants to keep data that isn't compliant in their situation → **we flag it and warn the user**
- All data is processed with compliance in mind; our output is compliant
- Human stays in the loop: AI suggests, user decides

## Pitch (PPT)
- **Hook:** "10 million – that's how much you can be fined for mishandling personal data."
- To do: find figures on **costs of data breaches**

> Note for fact-checking the hook: GDPR fines have two tiers – up to **€10 M or 2 %** of global annual turnover, and up to **€20 M or 4 %** for more serious violations (e.g. processing principles, legal basis). Under Swiss law (nDSG), fines of up to **CHF 250,000** can be imposed on responsible *individuals*. Worth verifying and citing the exact article before the pitch.

## Result / Demo
- Deployed as a **web page** so graders can use and test it directly
- Pop-up or info page explaining **what makes our solution special** and **how it works** (AI creates rules → deterministic engine applies them → compliant output + report)
