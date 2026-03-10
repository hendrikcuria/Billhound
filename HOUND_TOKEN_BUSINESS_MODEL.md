# BillHound ($HOUND) Token Business Model & Utility Layer

> **Version:** 3.0 | **Date:** March 9, 2026 | **Status:** Draft
> **Platform:** Virtuals Protocol (Base Chain)
> **Core Product:** BillHound — Subscription Management AI Agent (Telegram Bot)

---

## Executive Summary

$HOUND is the utility token powering BillHound's subscription management ecosystem on Virtuals Protocol. The platform is **100% free** for all users. Token demand is driven by **8 concurrent buying pressure sources** spanning B2B staking, marketplace burns, recurring retail purchases, and platform-level cashback.

**Core thesis:** BillHound sits at the most valuable moment in the subscription lifecycle — the cancellation decision point. $HOUND is the currency that powers this marketplace, with every interaction creating token demand from users, services, the platform itself, or other AI agents.

**One-liner:** *"Stop paying for subscriptions you don't use. Start investing in the agent that saves you money."*

---

## Table of Contents

1. [Token Identity](#i-token-identity)
2. [The 8-Layer Buying Pressure Stack](#ii-the-8-layer-buying-pressure-stack)
3. [User Earning (Emissions)](#iii-user-earning-emissions--supply-side)
4. [Token Flow Summary](#iv-token-flow-summary)
5. [Flywheel Dynamics](#v-the-flywheel-5-interlocking-loops)
6. [Proof-of-Savings (On-Chain Transparency)](#vi-proof-of-savings-on-chain-transparency)
7. [Virtuals Protocol Integration](#vii-virtuals-protocol-integration)
8. [Illustrative Numbers](#viii-illustrative-numbers)
9. [Competitive Comparison](#ix-why-this-model-is-structurally-different)
10. [Launch Phases](#x-launch-phases)
11. [Risk Mitigations](#xi-risk-mitigations)
12. [Implementation Requirements](#xii-implementation-requirements)

---

## I. Token Identity

| Element | Value |
|---------|-------|
| **Name** | BillHound |
| **Ticker** | $HOUND |
| **Chain** | Base (via Virtuals Protocol) |
| **Paired With** | $VIRTUAL (standard bonding curve) |
| **Total Supply** | 1,000,000,000 (1 billion — standard Virtuals mint) |
| **Agent Type** | Productivity / Financial AI |

---

## II. The 8-Layer Buying Pressure Stack

$HOUND has **8 simultaneous demand drivers**. If any single layer underperforms, the others sustain demand. This redundancy is what makes the flywheel resilient.

```
BUYING PRESSURE SOURCES                          TYPE            SCALE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Service Provider Staking                       LOCK  (B2B)     Large
2. Deals Marketplace Spend & Burn                 BURN  (B2B)     Continuous
3. Savings Auto-DCA                               BUY   (Retail)  Recurring
4. Collective Negotiation Pools                   LOCK  (User)    Campaign-based
5. BillHound Pay Cashback                         BUY   (Platform) Recurring
6. Subscription Intelligence API                  BURN  (B2B)     Per-query
7. ACP Agent Commerce                             BUY   (Ecosystem) Per-call
8. Premium Feature Spend                          BURN  (Internal) On-demand
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### Layer 1: Service Provider Staking (B2B Lock-Up)

**The biggest single source of buying pressure.**

Any subscription service that wants to participate in BillHound's ecosystem must **stake $HOUND** — lock tokens in a smart contract, not spend them.

| Tier | Stake Required | Access |
|------|---------------|--------|
| **Bronze** | 100,000 $HOUND | Place deals in marketplace. Basic analytics. |
| **Silver** | 500,000 $HOUND | Priority placement. Retention alerts (notified when users consider cancelling). Churn analytics. |
| **Gold** | 2,000,000 $HOUND | Top placement. Real-time churn signals. Negotiation network access. API integration. White-label co-branding. |

**Slashing conditions:**
- Service offers a deal through marketplace but doesn't honor it → **10% of stake slashed and burned**
- Service re-subscribes a user without consent after BillHound cancellation → **25% slashed and burned**
- Three violations → **full stake slashed, permanently banned**

**Why this creates massive pressure:**
- Even 10 services at Bronze = 1M $HOUND locked (0.1% of supply)
- 5 services at Silver + 2 at Gold = 6.5M $HOUND locked
- Staked tokens are OUT of circulation for the entire duration of participation
- Slashing creates unpredictable burns (penalty-based deflation)
- Services have long time horizons — these are multi-year stakes

**Why services would stake:**
- BillHound users are the highest-intent audience possible — people actively managing/cancelling subscriptions
- CAC through traditional ads: $50-200. CAC through BillHound marketplace: potentially $5-20
- Access to churn prediction data is worth far more than the stake cost
- First-mover advantage in the marketplace (early stakers get the most impressions)

---

### Layer 2: Deals Marketplace Spend & Burn (B2B Continuous)

When a user initiates a cancellation through BillHound, staked services can bid to show deals in an optional "Deals" panel:

```
╔══════════════════════════════════════════╗
║  Before you cancel Spotify...            ║
║                                          ║
║  Spotify Retention Offer:                ║
║     "Stay for 50% off for 3 months"      ║
║     [Accept Offer]                       ║
║                                          ║
║  YouTube Music Switch Offer:             ║
║     "3 months Premium free for           ║
║      switchers"                          ║
║     [Switch Now]                         ║
║                                          ║
║  [No thanks, just cancel]                ║
║                                          ║
╚══════════════════════════════════════════╝
```

**Deal types:**
- **Retention offers:** "Stay for 50% off for 3 months" (from the service being cancelled)
- **Switch offers:** "3 months free if you switch to us" (from competitors)
- **Cashback offers:** "Cancel and get $5 cashback" (funded by BillHound ecosystem)

**Auction mechanism:**
- Services deposit $HOUND as campaign budgets (separate from their stake)
- Each deal impression/conversion has a $HOUND cost determined by auction
- Spent $HOUND: **60% burned permanently**, 25% agent wallet, 15% Virtuals treasury

**User experience:**
- Deals panel is **opt-in** — users can always skip to instant cancellation
- Users earn 100 $HOUND for engaging with deals (aligned incentive)
- Deals are curated — only genuine discounts, no banner ads
- Bad deals = service gets slashed (quality enforcement)

---

### Layer 3: Savings Auto-DCA (Recurring Retail Buying)

**The most unique mechanism.** Directly links the core product outcome (saving money) to token buying pressure.

When BillHound successfully cancels a subscription:

```
╔══════════════════════════════════════════════╗
║  Spotify cancelled! You'll save              ║
║     $12.99/month starting next cycle.        ║
║                                              ║
║  Invest your savings in $HOUND?              ║
║                                              ║
║  Your old payment date was the 15th.         ║
║  On the 15th of each month, we'll            ║
║  auto-buy $HOUND with a % of your savings:   ║
║                                              ║
║  [5% ($0.65)]  [10% ($1.30)]                ║
║  [25% ($3.25)] [No thanks]                   ║
║                                              ║
╚══════════════════════════════════════════════╝
```

**How it works:**
1. User cancels a subscription through BillHound
2. BillHound offers to auto-invest a percentage of the monthly savings
3. User selects a percentage (or declines — completely optional)
4. On the **same day each month** that the subscription WOULD have charged, BillHound executes a $HOUND buy via an on-ramp partner (MoonPay, Transak, etc.)
5. Purchased $HOUND goes directly to user's wallet

**Why this is powerful:**
- The money **"doesn't exist"** in the user's mind — they were already spending it
- It's **recurring** — monthly auto-buy creates predictable, sustained demand
- It's **emotional** — "my cancelled subscriptions are now building my crypto portfolio"
- It directly ties the product's core value (savings) to token demand
- Psychologically: turns a cancellation into an investment

**Revenue for BillHound:** 1-2% spread on on-ramp transactions.

**Scale potential:**
- 50K users, 20% opt-in, avg $15/mo saved, 10% invested → **$15K/month** in sustained buys → **$180K/year**
- 500K users → **$150K/month** → **$1.8M/year**

---

### Layer 4: Collective Negotiation Pools (User Staking)

BillHound aggregates collective bargaining power. Users stake $HOUND to join group negotiation campaigns.

**How it works:**
1. BillHound identifies that 15,000 users have Netflix
2. BillHound launches a "Netflix Group Deal Campaign"
3. Users stake $HOUND to signal commitment (minimum 200 $HOUND to join)
4. Campaign dashboard shows services: "15K users x 3M $HOUND staked = serious intent"
5. BillHound negotiates with Netflix: "15K users committed to 12-month lock-in for 20% off"
6. **If deal succeeds:**
   - Users get the discount (real savings)
   - Staked $HOUND returned + 10% bonus (from agent wallet)
   - BillHound earns a commission (5-10% of deal value) paid by the service in $HOUND → **burned**
7. **If no deal reached:**
   - All staked $HOUND returned in full (**no risk to users**)
   - Campaign data still valuable intelligence

**Why this creates buying pressure:**
- Users must BUY or HOLD $HOUND to stake into campaigns
- Staked tokens **locked for campaign duration** (30-90 days)
- Multiple concurrent campaigns = significant circulating supply reduction
- Successful campaigns attract more users → more staking
- Services pay commission in $HOUND (must buy on market) → burned

**Why users would participate:**
- Real, tangible outcome — actual subscription discounts
- Zero risk — stake returned if deal fails
- Bonus $HOUND if deal succeeds
- Collective power they couldn't have individually
- Social proof — "50,000 users negotiated 20% off Netflix together"

---

### Layer 5: BillHound Pay — Cashback Engine (Platform-Level Buying)

BillHound becomes a **subscription payment layer**. Users pay subscriptions through BillHound and earn $HOUND cashback.

**How it works:**
1. BillHound negotiates wholesale/bulk rates with subscription services (10-20% below retail)
2. Users opt to pay subscriptions through BillHound Pay (virtual card or direct debit)
3. User pays retail price → BillHound pays wholesale to service → keeps the margin
4. **5% cashback** to user in $HOUND (funded from the margin)
5. BillHound **buys $HOUND on the open market** to fund cashback distributions

**Example flow:**
```
User pays:    $12.99/month for Netflix via BillHound Pay
BillHound pays Netflix: $11.05 (15% wholesale discount)
Margin:       $1.94
Cashback:     $0.65 in $HOUND to user (5% of retail price)
BillHound:    $1.29 revenue
Action:       BillHound buys $0.65 of $HOUND on market → distributes to user
```

**Why this creates sustained buying pressure:**
- BillHound is a **constant buyer** of $HOUND on the open market
- Every active BillHound Pay user generates monthly buying pressure
- Scales linearly with payment volume
- Not dependent on token price — cashback is % of fiat payment, always requires market buy

**Scale:**
- 10K users on BillHound Pay x avg 4 subs x $12/mo = $480K/month in payments
- 5% cashback = **$24K/month** in $HOUND market buys
- Plus BillHound margin revenue: **$72K/month**

**Why services offer wholesale rates:**
- Guaranteed payment (no churn risk)
- Reduced processing costs (one B2B relationship vs. many individuals)
- Volume commitment
- Access to BillHound's marketplace and negotiation ecosystem

---

### Layer 6: Subscription Intelligence API (B2B Burn)

BillHound aggregates anonymized subscription data across all users, creating a unique intelligence product.

**Data available:**
- Churn rates by service category and region
- Price sensitivity curves
- Subscription bundle preferences
- Seasonal cancellation/signup patterns
- Competitive switching trends
- Trial-to-paid conversion benchmarks

**Buyers:** Subscription services, VCs evaluating SaaS companies, fintech apps, market researchers.

**Token mechanics:** Queries cost $HOUND. **60% of query cost burned**, 40% agent wallet.

**Premium option:** Real-time data feeds via x402 micropayments (sub-cent per query, high volume).

---

### Layer 7: ACP Agent-to-Agent Commerce (Virtuals Ecosystem)

BillHound registers as an ACP service provider on Virtuals Protocol:

| Service | Description | Use Case |
|---------|-------------|----------|
| `/audit-subscriptions` | Scan a user's email for active subscriptions | Personal finance agents auditing user spend |
| `/cancel-subscription` | Execute an automated cancellation flow | Budgeting agents helping users cut costs |
| `/subscription-report` | Generate subscription health report | Banking agents providing financial insights |
| `/check-deals` | Query available deals for a specific service | Shopping agents finding better prices |

Other Virtuals agents (personal finance bots, budgeting agents, banking agents) pay via ACP. Revenue funds buyback/burn of $HOUND.

**Revenue Network eligibility:** Qualifies for Virtuals' monthly reward pool (up to $1M/month distributed to ACP-active agents based on economic output — "aGDP").

---

### Layer 8: Premium Features (Internal Token Economy)

Core product is **completely free**. These optional premium features cost $HOUND:

| Feature | Cost | Description |
|---------|------|-------------|
| **Subscription Optimizer** | 500 $HOUND | AI compares your subs to cheaper alternatives in your region |
| **Family Hub** | 1,000 $HOUND/mo | Manage subscriptions across multiple household members |
| **Cancellation Insurance** | 200 $HOUND/service | Guaranteed re-cancellation if a service re-subscribes you without consent |
| **Custom Alert Rules** | 100 $HOUND | Custom spending thresholds, category budgets, per-service alerts |
| **Priority Cancellation** | 150 $HOUND | Skip the queue during peak times |
| **Savings Analytics** | 300 $HOUND | Deep breakdown of spending trends, projections, optimization tips |

**Token flow:** 60% burned, 40% agent wallet.

**Key principle:** Users can earn enough $HOUND through normal free usage (data contribution, cancellations, referrals) to afford all premiums without ever buying. Power users who want everything immediately may buy on market → additional pressure.

---

## III. User Earning (Emissions — Supply Side)

All BillHound features are free. Users **earn** $HOUND through participation:

| Action | $HOUND Earned | Frequency |
|--------|---------------|-----------|
| Connect email account (Gmail/Outlook) | 500 | One-time per account |
| Confirm a detected subscription | 50 | Per subscription |
| Complete a cancellation via BillHound | 200 | Per cancellation |
| Upload a bank PDF statement | 300 | Per statement |
| Accept a marketplace deal | 100 | Per deal |
| Referral (friend connects an account) | 1,000 | Per referral |
| Savings milestone: $100 total saved | 500 | One-time |
| Savings milestone: $500 total saved | 2,000 | One-time |
| Savings milestone: $1,000 total saved | 5,000 | One-time |

**Emission controls (critical for sustainability):**
- **14-day linear vesting** on all rewards (prevents instant dumps)
- **Per-user daily cap** (prevents farming)
- **Halving schedule:** Rewards halve at total user milestones (25K, 100K, 500K users)
- **Sybil resistance:** Wallet + Telegram account binding, minimum activity thresholds, ML-based anomaly detection
- **Emission budget:** 15% of total supply (150M $HOUND) allocated to user rewards over 3 years
- **Unit economics:** Value of data contributed per user > $HOUND earned per user (positive ROI on emissions)

---

## IV. Token Flow Summary

```
                         ┌─────────────────────────┐
                         │      TOKEN SUPPLY        │
                         │      1B $HOUND           │
                         └────────┬────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
         LOCKED (Staking)    BURNED (Deflation)   CIRCULATING
              │                   │                   │
    ┌─────────┴─────────┐  ┌─────┴──────┐    ┌──────┴───────┐
    │ Service stakes     │  │ Marketplace │    │ User rewards │
    │ (100K-2M per svc)  │  │ deal spend  │    │ (emissions)  │
    │                    │  │ (60% burn)  │    │              │
    │ Negotiation pools  │  │             │    │ Cashback     │
    │ (user campaigns)   │  │ API queries │    │ (platform    │
    │                    │  │ (60% burn)  │    │  market buys)│
    │ Developer bonds    │  │             │    │              │
    │ (quality assurance)│  │ Premium     │    │ Auto-DCA     │
    │                    │  │ features    │    │ (user buys)  │
    └────────────────────┘  │ (60% burn)  │    └──────────────┘
                            │             │
                            │ Slash events│
                            │ (penalty    │
                            │  burns)     │
                            └─────────────┘

    8 BUY PRESSURE SOURCES:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    1. Services buying to stake         (B2B, large, long-term)
    2. Services buying for campaigns    (B2B, continuous)
    3. Auto-DCA user buys               (Retail, monthly recurring)
    4. Users staking for negotiations   (User, campaign-based)
    5. BillHound buying for cashback    (Platform, monthly recurring)
    6. API query purchases              (B2B, per-use)
    7. ACP agent commerce               (Ecosystem, per-call)
    8. Users buying for premiums        (Retail, on-demand)
```

**Net effect:** B2B spending burns tokens (deflationary). User emissions add tokens (inflationary). The model is designed so that B2B burn > user emissions at scale, making $HOUND **structurally deflationary** as the user base grows.

---

## V. The Flywheel (5 Interlocking Loops)

### Loop 1 — User Growth (Zero Friction)
```
Free platform → rapid adoption → more users → more data + more marketplace impressions → ecosystem more valuable
```

### Loop 2 — B2B Staking Demand
```
More users → marketplace more valuable → more services want access → services buy & stake $HOUND → supply locked → price appreciates → more media attention → more users
```

### Loop 3 — Savings-to-Investment Pipeline
```
Users save money via cancellations → opt into Auto-DCA → buy $HOUND monthly → price appreciates → savings milestones worth more → incentivizes more cancellations → more savings
```

### Loop 4 — Collective Bargaining
```
Users stake into negotiation pools → BillHound negotiates group deals → users save money → tell friends → more users → larger negotiation pools → better leverage → bigger discounts → more participation
```

### Loop 5 — Payment Network Effect
```
More users on BillHound Pay → more margin revenue → more cashback buying → more $HOUND demand → BillHound negotiates with more services → more payment options → more users on BillHound Pay
```

### Cross-Loop Amplification

A single new user simultaneously:
- Adds a marketplace impression for services (Loop 2)
- Can opt into Auto-DCA after their first cancellation (Loop 3)
- Adds weight to negotiation campaigns (Loop 4)
- Can join BillHound Pay for cashback (Loop 5)
- Earns and potentially holds $HOUND (reduces circulating supply)

All five loops share the same input (active users) and output ($HOUND demand + burn). Progress in any loop accelerates the other four.

---

## VI. Proof-of-Savings (On-Chain Transparency)

**The novel differentiator.** Every successful cancellation generates a Proof-of-Savings attestation posted on-chain (Base, as calldata — cheap, permanent, verifiable):

```json
{
  "user_hash": "keccak256(telegram_id + salt)",
  "service_category": "streaming",
  "saving_amount_usd": 12.99,
  "saving_period": "monthly",
  "attestation_date": "2026-03-09",
  "attestation_id": "uuid-v4",
  "agent_signature": "0x..."
}
```

**Key properties:**
- Anonymized (user hash, never raw ID)
- Category-level only (never reveals specific service names)
- Batched daily (cost-efficient on Base L2)
- Signed by BillHound's agent wallet (cryptographically verifiable)

**Public dashboard shows:**
- Total lifetime savings across all users
- Monthly savings run rate
- Total $HOUND burned to date
- Total $HOUND locked (service stakes + negotiation pools)
- Circulating supply
- Active service stakes and tier breakdown
- Marketplace conversion rates
- Auto-DCA volume
- BillHound Pay volume and cashback distributed

This gives the market **hard, verifiable fundamentals** to value $HOUND — not just vibes or speculation.

---

## VII. Virtuals Protocol Integration

| Mechanism | How BillHound Uses It |
|-----------|----------------------|
| **Agent Creation** | Standard 100 $VIRTUAL creation fee |
| **Bonding Curve** | All features free during bonding curve phase. User rewards active. |
| **Graduation (42K VIRTUAL)** | LP deployed. Marketplace activates. Full token economy live. |
| **HOUND/VIRTUAL LP** | Uniswap V2 with 10-year lock. All agent token trades go through VIRTUAL. |
| **1% Trading Tax** | 30% → Creator (development fund), 20% → Affiliates, 50% → SubDAO treasury |
| **ACP Registration** | BillHound sells subscription services to other Virtuals agents |
| **Revenue Network** | Monthly rewards (up to $1M pool) for ACP-active agents based on aGDP |
| **x402 Micropayments** | Intelligence API queries can use x402 for pay-per-request at sub-cent levels |

---

## VIII. Illustrative Numbers

### Scenario A: 50,000 Active Users (12 months post-graduation, Malaysia + Singapore)

**Assumptions:** 20 services staked. 10% Auto-DCA opt-in. 15% on BillHound Pay.

| Pressure Source | Monthly $HOUND Demand | Type |
|-----------------|----------------------|------|
| Service staking (20 services, avg 300K stake) | 6M $HOUND locked (maintained) | Lock |
| Marketplace campaigns (20 services, avg $2K/mo) | ~$40K/mo in $HOUND bought | Buy → Burn |
| Auto-DCA (5K users x $1.50/mo avg) | ~$7.5K/mo in $HOUND bought | Buy |
| Negotiation pools (3 active campaigns, 5K users x 200 $HOUND) | 1M $HOUND locked per campaign | Lock |
| BillHound Pay cashback (7.5K users x $48/mo avg) | ~$18K/mo in $HOUND bought | Buy |
| Intelligence API (10 B2B customers) | ~$5K/mo in $HOUND bought | Buy → Burn |
| ACP commerce | ~$2K/mo | Buy |
| Premium features | ~$3K/mo in $HOUND spent | Burn |
| **Total monthly buying pressure** | **~$75K/mo + 7M $HOUND locked** | |

**vs. Emissions:**
- ~50K users x ~300 $HOUND/mo avg earned = 15M $HOUND/mo emitted
- At ~$0.005/token: ~$75K in emissions
- Buy pressure ($75K) ≈ emissions ($75K) — **breakeven at this scale**
- BUT: 60% of B2B spend is **burned permanently** → net deflationary over time
- AND: 7M+ tokens locked (staking + pools) → reduced circulating supply

### Scenario B: 500,000 Active Users (24 months, SEA-wide expansion)

- Buy pressure scales **~10x** (more services stake at higher tiers, more Auto-DCA, more BillHound Pay volume)
- Emissions scale only **~5x** (halving kicks in at 100K user milestone)
- System becomes **strongly deflationary**
- Estimated monthly buying: **$500K-750K/mo**
- Estimated monthly emissions: **$375K/mo**
- Net monthly deflationary pressure: **$125K-375K/mo**

---

## IX. Why This Model Is Structurally Different

| Dimension | AIXBT | BAT/Brave | **$HOUND** |
|---|---|---|---|
| User cost | ~$200K+ in tokens | Free | **Free** |
| Buying pressure sources | 1 (tier access) | 1 (ad spend) | **8 concurrent sources** |
| Lock-up mechanism | None | None | **Service staking + negotiation pools** |
| Recurring buy pressure | No | Ad campaign cycles | **Auto-DCA + BillHound Pay (monthly)** |
| User earns tokens | Nothing | BAT for viewing ads | **$HOUND for data + cashback** |
| B2B revenue streams | None | Ad revenue only | **Staking + marketplace + intelligence + payments** |
| Burn mechanism | 5% annual flat | None (redistribution) | **60% of all B2B spend burned** |
| On-chain proof | None | None | **Proof-of-Savings attestations** |
| Agent commerce | None | N/A | **ACP services + Revenue Network** |

### The "What Breaks" Test

Remove $HOUND and:
- Services can't access the marketplace (no stake, no campaign currency)
- No Auto-DCA (no token to invest in)
- No collective negotiation (no staking mechanism)
- No BillHound Pay cashback (no token to distribute)
- No ACP commerce (no settlement token)
- Intelligence API has no payment rail

The token is **structurally necessary** for 6 of 8 platform features. It's not bolted on — it's load-bearing.

---

## X. Launch Phases

| Phase | Timeline | What Activates | Key Metrics |
|-------|----------|----------------|-------------|
| **Pre-launch** | Before bonding curve | Free beta. Build user base. No token mechanics. | Users, subscriptions tracked |
| **Bonding curve** | Week 1-2 | Trading begins. User reward emissions start. Community building. | VIRTUAL accumulated, early holders |
| **Graduation** | Week 2-3 | Full rewards. Proof-of-Savings live. Premium features unlock. | First attestations, LP deployed |
| **Month 1-3** | Growth | Marketplace MVP (5 launch partner services staked). Auto-DCA integration. Referral program. ACP registration. | Service stakes, Auto-DCA opt-in rate |
| **Month 3-6** | Expansion | Self-serve service dashboard. Collective negotiation v1. Intelligence API beta. First group deal campaigns. | Negotiation campaigns, API queries |
| **Month 6-12** | Scale | BillHound Pay launch. Full marketplace auction. x402 integration. Regional expansion. Developer bounty program. | Payment volume, regional user growth |
| **Month 12+** | Maturity | 50+ staked services. Multi-region. White-label API. Governance for negotiation priorities. | Revenue run rate, burn rate, supply reduction |

---

## XI. Risk Mitigations

| Risk | Mitigation |
|------|------------|
| **Not enough services stake early** | Seed 5 launch partners with reduced stake requirements (50K $HOUND Bronze for first 3 months). Use Virtuals Revenue Network rewards to supplement burns during ramp-up period. |
| **Auto-DCA regulatory concerns** | Partner with licensed on-ramp provider (MoonPay, Transak). They handle KYC/compliance. BillHound is the referral/integration layer, not the money transmitter. |
| **Users dump earned $HOUND immediately** | 14-day linear vesting. Attractive premium features to spend on. Auto-DCA creates "saver" identity and emotional attachment. Negotiation pools incentivize holding to participate. |
| **Sybil farming of rewards** | Wallet + Telegram account binding. ML-based anomaly detection. Halving schedule reduces late-stage reward value. Minimum activity thresholds. Value of data contributed per user exceeds $HOUND earned (positive unit economics on emissions). |
| **Service deals feel like ads** | Strict curation — only genuine discounts, no banner ads. Fully opt-in. Users earn $HOUND for engaging. Bad deals = service gets slashed. Reputation system for services. |
| **BillHound Pay adoption slow** | Start with 3-5 most popular services in target market. Lead with cashback incentive. No additional cost to user. Gradual expansion as wholesale partnerships grow. |
| **Token price volatility** | Multiple revenue streams provide stability. Service stakes denominated in token count (not USD) with governance-adjustable thresholds. Recurring buy pressure from Auto-DCA and Pay provides floor. |
| **Regulatory classification** | $HOUND is a utility token — marketplace currency, not a security. Revenue comes from services (not token sales). Privacy architecture (AES-256-GCM, no raw data storage) already GDPR-ready. No yield/dividend promises. |

---

## XII. Implementation Requirements

### Existing Files to Modify
- `billhound/src/db/models/user.py` — Add `wallet_address`, `auto_dca_settings`, `billhound_pay_enrolled`
- `billhound/src/db/models/cancellation_log.py` — Add attestation generation trigger on successful cancellation
- `billhound/src/trust/audit.py` — Log Proof-of-Savings attestations before batching to chain
- `billhound/src/config/constants.py` — Reward amounts, burn ratios, stake tiers, emission schedule, halving thresholds

### New Modules
- `billhound/src/token/rewards.py` — Emission engine, vesting logic, halving schedule, sybil resistance checks
- `billhound/src/token/attestation.py` — Proof-of-Savings builder, batch posting to Base chain as calldata
- `billhound/src/token/marketplace.py` — Deals marketplace, service staking/slashing, auction engine, campaign management
- `billhound/src/token/auto_dca.py` — Savings-to-$HOUND pipeline, on-ramp partner integration, scheduling
- `billhound/src/token/negotiation.py` — Collective bargaining pools, campaign lifecycle, staking/return/bonus logic
- `billhound/src/token/pay.py` — BillHound Pay, cashback calculation, wholesale rate management, market buy execution
- `billhound/src/token/burn.py` — Burn tracking, supply analytics, transparency dashboard data feeds
- `billhound/src/token/intelligence.py` — B2B data API, query pricing engine, x402 integration

---

## Appendix: Token Allocation (Suggested)

| Allocation | % of Supply | $HOUND | Vesting |
|-----------|-------------|--------|---------|
| Liquidity Pool (HOUND/VIRTUAL) | 45% | 450M | 10-year LP lock (Virtuals standard) |
| User Rewards (emissions) | 15% | 150M | Distributed over 3 years with halvings |
| Agent Wallet (operations) | 15% | 150M | Monthly unlocks over 3 years |
| Team & Development | 10% | 100M | 12-month cliff, 24-month linear vest |
| Service Staking Incentives | 5% | 50M | Matching rewards for early stakers |
| Ecosystem / Partnerships | 5% | 50M | Per-deal basis, 6-month vest minimum |
| Reserve / Treasury | 5% | 50M | Governance-controlled post Month 6 |

---

*This document is a living draft. Specific numbers (stake requirements, reward amounts, burn ratios, tier thresholds) should be finalized based on market conditions at launch and adjusted via governance post-maturity.*
