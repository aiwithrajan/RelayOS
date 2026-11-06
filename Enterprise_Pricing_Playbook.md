# RelayOS — Enterprise Commercial Pricing & Governance Playbook

> **Document ID:** `DOC-POL-2026-PLAYBOOK-V2`  
> **Classification:** Internal Commercial Policy (Enforced Deterministically by `@deal-desk`)  
> **Status:** Active & Legally Binding  
> **Control Plane:** Switch Deal Room `#acme-fintech-closing`

---

## 1. Executive Purpose & Governance Scope

This Playbook establishes the strict, non-negotiable commercial governance policies and automated mathematical rules that dictate how enterprise contracts are priced, discounted, approved, and fulfilled within **RelayOS**.

All enterprise deal terms must be evaluated against this Playbook by the `@deal-desk` AI financial agent before any customer proposal can be unlocked or signed.

> [!IMPORTANT]
> **Deterministic Execution (Zero Hallucination Risk)**:  
> Commercial rules are evaluated strictly by deterministic mathematical code (`core/playbook_engine.py`). No LLM decision-making or stochastic generation is permitted in financial calculations or margin checks.

---

## 2. FastMCP Privilege & Security Isolation (AT-6)

RelayOS enforces strict dual-agent separation of duties under FastMCP:

| Agent / Role | Scope & Permissions | Playbook & Financial Authority |
| :--- | :--- | :--- |
| **`@deal-desk`** | Financial governance, compliance evaluation, tenant provisioning, PDF generation, Stripe invoicing. | **Full Authority**: Reads Playbook, runs `check_playbook`, and executes money/fulfillment tools once customer signs. |
| **`@architect`** | Integration engineering, ERP adapter code in `./relayos-app`, running unit tests. | **Strictly Forbidden (HTTP 403)**: Cannot read Playbook rules, cannot access financial tools, and cannot invoke billing or provisioning APIs. |
| **`Customer Champion`** | Reviews sanitized proposal at `/t/acme`, signs agreement, views deliverables. | **Zero Visibility**: No visibility into internal gross margins, infrastructure cost models, or admin controls. |

---

## 3. Commercial Playbook Rules (R1 – R5)

Every enterprise proposal is evaluated against five deterministic rules. An overall deal passes **only if all five rules evaluate to PASS**.

### **Rule R1: Gross Margin Floor ($\ge 75.0\%$)**
- **Policy Statement**: The gross margin on every enterprise deployment must meet or exceed $75.0\%$.
- **Mathematical Formula**:
  $$\text{Gross Margin} = \frac{\text{Annual Contract Price} - \text{Annual Infra Cost}}{\text{Annual Contract Price}}$$
- **Enforcement**:
  - If $\text{Margin} \ge 0.750$ $\implies$ **PASS**
  - If $\text{Margin} < 0.750$ $\implies$ **FAIL** *(Escalated to Founder for counter-offer or rejection)*

---

### **Rule R2: Maximum Discount Authority ($\le 10.0\%$)**
- **Policy Statement**: The standard enterprise catalog list price is **$\$24,000$ / year**. Deal desk agents are authorized to grant discounts up to a maximum of **$10.0\%$** without executive board sign-off.
- **Price Floor**:
  $$\text{Minimum Autonomous Price Floor} = \$24,000 \times (1 - 0.10) = \mathbf{\$21,600 / \text{year}}$$
- **Enforcement**:
  - If $\text{Annual Price} \ge \$21,600$ $\implies$ **PASS**
  - If $\text{Annual Price} < \$21,600$ $\implies$ **FAIL** *(Discount exceeds 10.0%; requires founder revision)*

---

### **Rule R3: Setup & Onboarding Fee Waiver Policy**
- **Policy Statement**: Standard enterprise onboarding and integration provisioning carries a mandatory **$\$2,500$ setup fee**.
- **Waiver Criteria**: The setup fee may be waived automatically if and only if:
  1. The annual contract price is **$\ge \$20,000$**, AND
  2. The contract commitment term is **$\ge 12$ months**.
- **Enforcement**:
  - Fee not waived $\implies$ **PASS**
  - Fee waived AND ($\text{Price} \ge \$20,000$ and $\text{Term} \ge 12$) $\implies$ **PASS**
  - Fee waived AND ($\text{Price} < \$20,000$ or $\text{Term} < 12$) $\implies$ **FAIL**

---

### **Rule R4: Payment Terms & Working Capital Policy**
- **Policy Statement**: Standard commercial settlement cycle is **Net-30**. Fast payment terms (**Net-15**) are encouraged and pre-authorized to accelerate cash conversion. Extended terms (**Net-60** or longer) require explicit CFO / Founder exception.
- **Enforcement**:
  - Payment Terms $\in \{\text{"Net-15"}, \text{"Net-30"}\}$ $\implies$ **PASS**
  - Payment Terms $\notin \{\text{"Net-15"}, \text{"Net-30"}\}$ $\implies$ **FAIL**

---

### **Rule R5: White-Label Branding & Domain Routing Policy**
- **Policy Statement**: Dedicated white-label multi-tenant routing (e.g., custom isolated portal at `/t/{slug}`) is restricted exclusively to **Enterprise Tier** customers.
- **Enforcement**:
  - Tier == Enterprise $\implies$ **PASS**
  - Non-Enterprise tiers requesting white-label $\implies$ **FAIL**

---

## 4. Deterministic Infrastructure Cost Model

Infrastructure costs are computed mathematically based on allocated peak rate limits:

$$\text{Annual Infra Cost (USD)} = \$1,000 + (\$7 \times \text{Allocated RPM})$$

Where:
- **$\$1,000$**: Fixed annual overhead for dedicated compute worker and isolated database tenant namespace.
- **$\$7$ / RPM**: Variable annual capacity cost per sliding-window request/minute unit.

### Examples:
- **1,000 RPM (Initial Customer Ask)**:
  $$\text{Cost} = \$1,000 + (\$7 \times 1,000) = \mathbf{\$8,000 / \text{year}}$$
- **600 RPM (Balanced Enterprise Counter)**:
  $$\text{Cost} = \$1,000 + (\$7 \times 600) = \mathbf{\$5,200 / \text{year}}$$
- **800 RPM (High-Throughput Spikes)**:
  $$\text{Cost} = \$1,000 + (\$7 \times 800) = \mathbf{\$6,600 / \text{year}}$$

---

## 5. Scenario Evaluation & Decision Matrix

| Metric / Rule | Acme Initial Ask (DealSpec v1) | Founder Counter (DealSpec v2) | Customer Auto-Pass (DealSpec v2) |
| :--- | :--- | :--- | :--- |
| **Annual Price** | $\$20,000$ | $\$22,000$ | $\$23,000$ |
| **Rate Limit Quota** | $1,000$ RPM | $600$ RPM | $600$ RPM |
| **Payment Terms** | Net-30 | Net-15 | Net-30 |
| **Calculated Infra Cost**| $\$8,000$ | $\$5,200$ | $\$5,200$ |
| **Gross Margin** | **60.0%** | **76.4%** | **77.4%** |
| **R1: Margin Floor $\ge 75\%$** | ❌ **FAIL** ($60.0\% < 75\%$) | ✅ **PASS** ($76.4\% \ge 75\%$) | ✅ **PASS** ($77.4\% \ge 75\%$) |
| **R2: Discount $\le 10\%$** | ❌ **FAIL** ($16.7\% > 10\%$) | ✅ **PASS** ($8.3\% \le 10\%$) | ✅ **PASS** ($4.2\% \le 10\%$) |
| **R3: Setup Fee Waiver** | ✅ **PASS** ($\ge \$20\text{k}, 12\text{mo}$) | ✅ **PASS** ($\ge \$20\text{k}, 12\text{mo}$) | ✅ **PASS** ($\ge \$20\text{k}, 12\text{mo}$) |
| **R4: Payment Terms** | ✅ **PASS** (Net-30) | ✅ **PASS** (Net-15) | ✅ **PASS** (Net-30) |
| **R5: White-Label** | ✅ **PASS** (Enterprise) | ✅ **PASS** (Enterprise) | ✅ **PASS** (Enterprise) |
| **Final Playbook Verdict**| 🚫 **BLOCKED (Audit Flagged)** | ⚡ **PASSED (Founder Approved)** | ⚡ **PASSED (Auto-Approved)** |

---

## 6. Audit Logging & Compliance Ledger

Every execution of `check_playbook` records an immutable audit entry in `relayos.db` (`audit_logs`):

```json
{
  "deal_id": "acme-2026-11",
  "actor": "@deal-desk",
  "action": "CHECK_PLAYBOOK",
  "status": "PASS",
  "details": {
    "version": 2,
    "margin": 0.764,
    "rules": {
      "R1": "pass",
      "R2": "pass",
      "R3": "pass",
      "R4": "pass",
      "R5": "pass"
    },
    "note": "Founder counter-offer passes all playbook rules (margin 76.4% >= 75%, discount 8.3% <= 10%)"
  }
}
```

This audit trail ensures full transparency for financial audits, investor reporting, and revenue operations.
