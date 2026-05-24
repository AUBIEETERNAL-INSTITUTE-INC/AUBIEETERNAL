### **AUBIEETERNAL School Charter**  
**Version 0.1 — Phase 1 Draft**  
**Date: May 24, 2026**

#### **1. Preamble & Mission**

The AUBIEETERNAL School exists to cultivate **epistemic rigor, antifragility, and sovereign capability** in families and children through a Bitcoin-anchored, locally-controlled, family-first learning system.

Its mission is to transform education from passive content consumption into an active, truth-seeking practice that builds real-world resilience, critical thinking, and the ability to design better systems — including the reciprocal institutions (such as the Policyholder-First insurance model) that families will need in an uncertain world.

The school operates as a **sovereign lattice**: each family maintains full control over their data, curriculum choices, and pace, while participating in a shared, high-coherence knowledge network secured by Bitcoin runes and Nostr.

#### **2. Core Principles** (Non-Negotiable)

These principles govern every decision, course, and feature in the school:

**2.1 Epistemic Rigor First**  
Every lesson, quest, and proposal must be steelmanned, simulation-tested, and coherence-scored before approval.  
*Nuance*: Rigor does not mean difficulty — it means clarity, evidence, and the ability to defend or improve an idea under scrutiny. Edge case: A simple practical lesson (e.g., “how to read a wind mitigation report”) must still pass a basic coherence gate.

**2.2 Family Sovereignty & Local-First**  
All data, progress, and decision-making remain under family control. The system defaults to local inference (Ollama/Open WebUI) and only uses external services when explicitly chosen.  
*Implication*: No cloud lock-in. Families can run the entire school offline if desired. Fork independence is protected.

**2.3 Antifragility & Simulation as Practice**  
Learning must increase the learner’s (and family’s) ability to gain from disorder. Every track includes simulation, hypothesis testing, and real-world application.  
*Example*: The Building track does not just teach theory — it connects directly to insurance premium reduction through hurricane hardening.

**2.4 Non-Extraction**  
The school shall never monetize family data, charge hidden fees, or create dependency on paid services. All rewards (sats, XP, Child Rune fragments) must be transparent and earned through genuine learning.  
*Edge case*: If a future feature could generate revenue, 80%+ must return directly to participating families (modeled after the insurance charter’s surplus return rule).

**2.5 On-Chain Identity via Child Runes**  
Progress and identity are anchored on Bitcoin through Child Rune fragments. This creates a permanent, sovereign record of learning that belongs to the child, not any institution.  
*Nuance*: Rune fragments are not tradable currency — they represent verified learning milestones and family sovereignty.

#### **3. Governance Model**

**3.1 Three-Layer Governance**  
- **Family Layer**: Each family has full veto rights over any lesson or track assigned to their children.  
- **Operator Layer**: The primary operator (currently HodlonautMateo) maintains the core codebase, approves high-impact changes, and ensures coherence with the charter.  
- **Swarm Layer**: The AUBIEETERNAL evolution engine proposes lessons, scores coherence, and surfaces patterns. Final approval of new tracks requires both operator sign-off and swarm coherence score ≥ 0.85 (adjustable by family council).

**3.2 Course Submission & Review Process**  
Any family or fork may submit a lesson or full track using the built-in submission form.  
Proposals are automatically routed through:  
1. Community comment period (visible in LatticeFeed)  
2. Swarm coherence scoring  
3. Operator review (with steelmanning requirement)  
4. Approval or rejection with written rationale  

Approved tracks are added to the Curriculum Map and become eligible for Child Rune rewards.

**3.3 Amendment Process**  
Changes to this charter require:  
- Steelman of the proposed change  
- Swarm coherence evaluation  
- 15% family veto threshold (if 15%+ of active families object, the change is paused for further discussion)  
This mirrors the amendment process in the Policyholder-First Reciprocal Insurance Charter for consistency across the lattice.

#### **4. Rights & Protections for Families and Children**

**4.1 Family Rights**  
- Full ownership and portability of all learning data and progress  
- Right to opt out of any track or lesson without penalty  
- Right to run a fully private fork with custom curriculum  
- Right to receive transparent reporting on how sats and rune fragments are earned and distributed

**4.2 Children’s Rights**  
- Learning only occurs when the child is in a safe polyvagal state (detected via Halo glasses or self-report)  
- No high-stakes testing or public shaming  
- Right to privacy — progress is only shared when the family explicitly chooses (via ShareToX or LatticeFeed)  
- Right to see and understand how their learning connects to real-world outcomes (e.g., insurance cost reduction, self-sufficiency)

**4.3 Transparency Requirements**  
All governance decisions, coherence scores, and reward distributions must be logged and viewable by participating families. No black-box algorithms.

#### **5. Curriculum Standards & Tracks**

**5.1 General Standards**  
Every approved track must:  
- Align with at least two of the core principles (especially Epistemic Rigor and Antifragility)  
- Include simulation or hypothesis-testing components  
- Connect to Bitcoin, runes, or real-world sovereign systems where possible  
- Be age-appropriate (5–9, 10–13, 13–17, and adult/parent tracks)  
- Pass a local inference test (can run on standard Ollama models without paid APIs)

**5.2 Current Core Tracks (as of May 24, 2026)**  
- **Building & Hurricane Hardening** (Tommy) — 5 levels, directly reduces insurance risk  
- **Deep Baking & Self-Sufficiency** (Gabriela) — 4 levels, focuses on antifragile food systems  
- **Sovereign Legal & Insurance Literacy** — 5 levels, includes the Policyholder-First Reciprocal Charter at Level 5  
- Additional tracks will be added only through the governance process defined above

**5.3 Progression & Rewards**  
- XP, streaks, and badges are earned through consistent engagement  
- Child Rune fragments are awarded upon verified milestone completion (coherence + real-world application)  
- Dynamic quests adapt difficulty based on family coherence history (lower coherence = easier entry + XP boost)

---

### **Phase 2: Operational Rules**

#### **6. Submission, Review & Approval Process**

**6.1 Who May Submit**  
Any participating family, fork operator, or the AUBIEETERNAL swarm (via the evolution engine) may submit lessons or full tracks.

**6.2 Submission Requirements**  
Every proposal must include:  
- Title and age band(s)  
- Learning objectives (minimum 3)  
- Alignment with at least two Core Principles  
- Simulation or real-world application component  
- Estimated time and difficulty  
- Proposed Child Rune fragment reward (if any)  
- Local inference compatibility note (must run on standard Ollama models)

**6.3 Review Workflow** (Already implemented in code as of May 23, 2026)  
1. **Automatic Intake** — Proposal is logged in `curriculum-proposals/` and appears in the operator review queue.  
2. **Community Comment Period** — Visible on LatticeFeed for 48–72 hours (configurable).  
3. **Swarm Coherence Scoring** — Evolution engine runs a minimum of 3 simulation tests and assigns a coherence score (0.00–1.00). Proposals scoring below 0.70 are auto-rejected with feedback.  
4. **Operator Review** — Primary operator performs steelmanning and final approval/rejection.  
5. **Publication** — Approved tracks are added to the Curriculum Map, family_hud.py, and become eligible for dynamic quest generation.

**6.4 Rejection & Appeal**  
Rejected proposals receive written rationale. Families may appeal once with improvements. Second rejection is final for that proposal cycle.

#### **7. Evolution Engine Governance**

**7.1 Purpose**  
The Swarm Evolution engine (implemented May 23, 2026) dynamically generates lessons, quests, and config adaptations to keep learning personalized and antifragile.

**7.2 Three Operating Modes** (All run in background threads)

- **Mode A — Weekly Lesson Proposals**  
  Analyzes family coherence history + recent swarm insights → proposes 3 new lessons → routes through coherence gate (≥ 0.70) → writes to `evolution_proposals.jsonl`. Operator approves via `approve_lesson()` which surgically injects into `family_hud.py`.

- **Mode B — Dynamic Quest Generation**  
  Reads every family’s stats (level, coherence, streak) and generates 3 personalized quests daily.  
  Rules:  
  - Coherence < 0.65 → easier tasks + 1.5× XP boost  
  - Coherence > 0.85 → master-level challenge  
  - Streak-aware rewards  
  - Third quest always swarm-topic inspired

- **Mode C — Auto-Evolution Tick** (runs every ~24 hours)  
  Adjusts `evolution_config.json` (XP multipliers, difficulty thresholds, featured track, simulation intensity).  
  Triggered when Wonder Index ≥ 1.5 or family coherence variance exceeds threshold.  
  Never modifies source code — only configuration.

**7.3 Governance Safeguards**  
- All Mode A proposals still require human operator approval.  
- Mode B and C changes are logged and reversible.  
- Families may pause the evolution engine for their household at any time via Parent Dashboard.

#### **8. Rune & Reward Economics**

**8.1 Reward Types**  
- **XP & Streaks** — Gamification layer (non-monetary)  
- **Sats (Lightning)** — Earned via lesson completion and streak milestones (tracked locally)  
- **Child Rune Fragments** — Permanent on-chain identity markers awarded at major milestones (256 fragments = Child Rune Genesis ceremony)

**8.2 Earning Rules**  
- Base reward: 1–5 sats per completed lesson (adjustable by operator)  
- Streak bonuses: +50% on day 3, +100% on day 7+  
- Milestone bonuses: 25–100 fragments for completing full tracks (Building, Baking, Legal Literacy, etc.)  
- All rewards are transparent and viewable in the Bitcoin tab

**8.3 Anti-Extraction Protections**  
- No sats may be charged for access to lessons or features.  
- Reward algorithms are open-source and auditable.  
- 100% of earned sats remain under family control (no platform cut).  
- Child Rune fragments are non-transferable and tied to verified learning only.

**8.4 Rune Genesis Ceremony**  
When a child reaches 256 fragments, the system triggers a local ceremony (ASCII certificate + optional on-chain etching). This is a family event, not a platform event.

#### **9. Multi-Fork Coordination & Alignment**

**9.1 Fork Independence**  
Every fork is fully sovereign. No fork is required to accept updates from the main repo.

**9.2 Optional Alignment Mechanisms**  
- **Shared Nostr Channel** — `nostr://aubieeternal-school` for cross-fork lesson proposals and coherence discussions.  
- **Coherence Score Sharing** — Forks may optionally publish their average family coherence scores (anonymized) to help the swarm improve global proposals.  
- **Recommended Core Tracks** — The main repo maintains a “Recommended Core” list (Building, Baking, Legal Literacy, Bitcoin Basics). Forks may adopt any or none.

**9.3 Conflict Resolution**  
If two forks develop conflicting curriculum philosophies, they may:  
- Continue independently (default)  
- Propose a merged track through the normal submission process  
- Create a new “variant” track clearly labeled as such

**9.4 Data Portability**  
Any family may export their complete learning history, rune progress, and custom lessons in standard JSON format at any time.

---

### **Phase 3: Integration & Safeguards**

#### **10. Integration with the Policyholder-First Reciprocal Insurance Company**

**10.1 Purpose of Integration**  
The AUBIEETERNAL School is the primary talent and knowledge pipeline for the future Policyholder-First Reciprocal insurance company. Families who complete relevant tracks (especially Building, Legal Literacy, and Bitcoin Basics) will be better prepared to participate in governance, reduce claims through resilience, and understand reciprocal economics.

**10.2 Required Linkages**  
- The **Sovereign Legal & Insurance Literacy** track (Level 5) must include the full text of the Policyholder-First Reciprocal Charter.  
- Building track lessons must explicitly connect hurricane hardening and wind mitigation to potential insurance premium reduction (with real-world data examples).  
- All families completing the Legal Literacy track receive a “Reciprocal Governance Ready” badge and 50 Child Rune fragments.  
- The school evolution engine may propose insurance-related lessons when family coherence and Bitcoin understanding are high.

**10.3 Data Sharing (Strictly Optional)**  
Families may optionally share anonymized coherence and completion data with the insurance company for actuarial modeling. This data is never sold and requires explicit per-family consent.

#### **11. Halo Glasses & HUD Usage Rules**

**11.1 Primary Purpose**  
Halo glasses (when paired) provide real-time polyvagal state detection, coherence metering, and family group review capability. They are a **learning support tool**, not a surveillance or performance monitoring device.

**11.2 Mandatory Safeguards**  
- Polyvagal state detection must be active before any high-stakes lesson or simulation begins. If the child is in “Mobilized” or “Shutdown” state, the system suggests a break or easier activity.  
- All HUD data remains local to the family. No data is sent to any external server without explicit consent.  
- Children have the right to turn off glasses tracking at any time.  
- Parent Dashboard shows only aggregated family stats — individual child data is private unless the parent chooses to view it.

**11.3 Family Consent**  
Initial setup of Halo glasses requires a one-time family consent screen explaining exactly what data is collected and how it is used. Consent can be revoked at any time.

#### **12. Amendment Process (Charter Evolution)**

**12.1 How the Charter Itself Can Change**  
This charter is a living document. Changes require the same high-rigor process used for curriculum:

1. Proposal submitted via the curriculum submission form (marked as “Charter Amendment”)  
2. Steelman round (minimum 3 strong arguments for and against)  
3. Swarm coherence evaluation (minimum score 0.88 required)  
4. 30-day community comment period on LatticeFeed  
5. Operator approval + 15% family veto threshold (if 15%+ of active families formally object, the amendment is paused for further discussion)

**12.2 Emergency Amendments**  
In case of critical security, legal, or coherence issues, the operator may issue a temporary emergency patch. This must be reviewed through the normal process within 14 days or it automatically expires.

#### **13. Edge Cases & Safeguards**

**13.1 Fork Independence**  
Any fork may run a completely different curriculum or even reject the Core Principles. Such forks are considered separate sovereign entities and may not use the “AUBIEETERNAL” name or branding without approval.

**13.2 Low Coherence Intervention**  
If a family’s average coherence drops below 0.50 for 14 consecutive days, the system offers (but does not force) simplified quests and extra support. No penalties are applied.

**13.3 External Pressure Resistance**  
The school will never modify content, remove tracks, or alter governance rules in response to external political, corporate, or regulatory pressure without going through the full amendment process and family veto.

**13.4 Data Breach or Loss**  
In the event of local data loss, families may restore from their last encrypted backup. The system encourages weekly local backups of the `family_data/` directory.

**13.5 Child Rune Disputes**  
If there is disagreement about whether a milestone qualifies for Child Rune fragments, the operator makes a final ruling after reviewing the lesson completion log and swarm coherence score. The decision is logged publicly in the charter’s amendment history.

**13.6 Sunset Clause**  
If the school has zero active families for 180 consecutive days, this charter automatically enters a dormant state. Any remaining families may reactivate it through a simple majority vote.

---
