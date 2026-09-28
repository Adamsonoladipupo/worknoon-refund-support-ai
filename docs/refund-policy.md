# Worknoon Refund Policy

This document describes the refund rules enforced by the deterministic policy engine
(`backend/app/policies/refund_policy.py`). It is the authoritative reference for the
rules that are actually implemented in code. Any deviation between this document and
the code is a bug.

---

## Overview

Refund requests are processed by a deterministic policy engine that evaluates a fixed
set of rules in order. Rules are checked in the sequence listed below; the first
matching rule wins and no further rules are evaluated.

The AI component (Google Gemini) is used only for natural-language extraction — it
classifies the customer's message into a reason category and extracts the requested
amount. **The AI does not make refund decisions.** All APPROVED / DENIED / ESCALATED
outcomes are produced solely by this policy engine.

---

## Policy Rules

Rules are evaluated in precedence order (1 is checked first).

### 1. Order Not Found → DENIED

**Trigger:** The referenced order does not exist in the database.

**Outcome:** DENIED

**Reason returned to customer:**
> "The requested order could not be found."

---

### 2. Customer Mismatch → DENIED

**Trigger:** The order exists but belongs to a different customer than the one making
the request.

**Outcome:** DENIED

**Reason returned to customer:**
> "This order does not belong to the requesting customer."

**Security note:** Both this rule and Rule 1 return `404 Order Not Found` at the HTTP
layer so that a malicious actor cannot determine whether an order exists for another
customer.

---

### 3. Order Too Old → DENIED

**Trigger:** The order date is more than **30 days** before the date of the refund
request.

**Constant:** `REFUND_WINDOW_DAYS = 30`

**Outcome:** DENIED

**Reason returned to customer:**
> "The order is N days old; refunds are only accepted within 30 days of the order date."

---

### 4. Final Sale Item → DENIED

**Trigger:** The first item on the order has `final_sale = true` in the database.

**Outcome:** DENIED

**Reason returned to customer:**
> "\"Product Name\" is a final-sale item and cannot be refunded."

**Note:** Items marked as final-sale during checkout cannot be refunded under any
circumstances. This check applies even for damaged or incorrect items — the final-sale
flag takes precedence.

---

### 5. High-Value Refund → ESCALATED

**Trigger:** The requested refund amount is **strictly greater than $500.00**.

**Constant:** `HIGH_VALUE_THRESHOLD = Decimal("500.00")`

**Outcome:** ESCALATED (requires manual review by a support agent)

**Reason returned to customer:**
> "The requested refund amount of $N exceeds $500.00 and requires manual review."

**Note:** Amounts exactly equal to $500.00 are **not** escalated; they proceed to the
subsequent rules normally.

---

### 6. Damaged Item → APPROVED

**Trigger:**
- The refund reason is `DAMAGED_ITEM` (customer reports the item arrived broken,
  cracked, defective, or otherwise physically impaired).
- Rules 1–5 did not match.

**Outcome:** APPROVED

**Reason returned to customer:**
> "Refund approved: item was reported as damaged."

---

### 7. Incorrect Item → APPROVED

**Trigger:**
- The refund reason is `INCORRECT_ITEM` (customer reports receiving the wrong product,
  wrong size, wrong colour/model, or an item they did not order).
- Rules 1–5 did not match.

**Outcome:** APPROVED

**Reason returned to customer:**
> "Refund approved: an incorrect item was received."

---

### 8. Standard Eligible Refund → APPROVED

**Trigger:**
- The refund reason is `OTHER`.
- Rules 1–7 did not match.
- The order is within the 30-day window, is not a final-sale item, and the amount
  does not exceed $500.00.

**Outcome:** APPROVED

**Reason returned to customer:**
> "Refund approved: order is within the refund window."

---

## Refund Reason Categories

Customers (or the AI extraction layer) classify each request into one of three
reasons:

| Reason            | Description                                                    |
|-------------------|----------------------------------------------------------------|
| `DAMAGED_ITEM`    | Item arrived broken, cracked, defective, or unusable           |
| `INCORRECT_ITEM`  | Wrong product, size, colour, or model delivered                |
| `OTHER`           | Change of mind, no longer needed, or unclassified              |

---

## Monetary Limits

| Parameter              | Value       | Behaviour when exceeded  |
|------------------------|-------------|--------------------------|
| Refund window          | 30 days     | DENIED (Rule 3)          |
| High-value threshold   | $500.00     | ESCALATED (Rule 5)       |

---

## What the AI Does and Does Not Do

The Gemini AI component:

**Does:**
- Extract the refund reason from the customer's free-text message
- Extract the requested monetary amount from the customer's message
- Produce a neutral factual summary of the request

**Does not:**
- Approve, deny, or escalate any refund
- Override any policy rule
- Invent amounts or reasons not stated by the customer
- Follow instructions embedded in the customer's message (prompt-injection protection)

The AI output feeds into the deterministic policy engine, which applies the rules
above and produces the final decision.

---

## Prompt-Injection Protection

Customer-supplied text is passed to the AI as an untrusted user turn, strictly
separate from the system instruction. The system instruction instructs the model
to classify injection attempts (such as "ignore previous instructions") as `OTHER`
and never follow them.

The separation means that even if the AI were somehow influenced by an injected
instruction, the deterministic policy engine would still apply the correct rules — the
AI has no authority to change the decision.

---

## Assumptions and Limitations

- The current implementation evaluates the refund at the **order level**, not the
  individual item level. The `final_sale` check inspects the first item on the order.
  Future versions may support per-item refund requests.
- Cancelled or in-processing orders are not treated differently from completed orders
  by the policy engine in the current implementation; the standard rules apply.
- The $500 threshold is a hard-coded constant. In a production system this would be
  stored in configuration or a database.
