/**
 * Development-only test scenario definitions.
 *
 * Each scenario pre-populates the refund form with data that exercises a
 * specific backend code path.  All data is submitted to the real backend —
 * no responses are mocked or faked.
 *
 * UUIDs are taken directly from the seeded database (scripts/seed.py):
 *   Customer 1 — Alice Thornton  — 00000000-0000-0000-0000-000000000001
 *   ORD-1001    — 8 days old      — 10000000-0000-0000-0000-000000001001 (APPROVED)
 *   ORD-1002    — 48 days old     — 10000000-0000-0000-0000-000000001002 (DENIED)
 *
 * This file must only be imported inside an `import.meta.env.DEV` guard.
 * It is never included in production builds because Vite's tree-shaker
 * eliminates the guarded branch.
 */

import type { RefundReason } from './api/types'

// ---------------------------------------------------------------------------
// Scenario shape
// ---------------------------------------------------------------------------

/** Identifies which submission mode the scenario targets. */
export type ScenarioMode = 'structured' | 'ai'

/** The form fields that a scenario can populate. */
export interface ScenarioFormPatch {
  customerId?: string
  orderId?: string
  requestedAmount?: string
  reason?: RefundReason
  message?: string
}

export interface TestScenario {
  /** Short label shown in the selector button. */
  label: string
  /** One-line description of what outcome to expect. */
  description: string
  /** Which submission mode to switch to (undefined = keep current). */
  mode?: ScenarioMode
  /** Form fields to populate. Omitted keys are left unchanged. */
  form: ScenarioFormPatch
  /** If true, also clears the result and error panels. */
  clearResult?: boolean
}

// ---------------------------------------------------------------------------
// Seeded customer / order UUIDs
// ---------------------------------------------------------------------------

const ALICE_ID = '00000000-0000-0000-0000-000000000001'

/** ORD-1001 — 8 days old — within the 30-day refund window → APPROVED */
const ORDER_WITHIN_WINDOW = '10000000-0000-0000-0000-000000001001'

/** ORD-1002 — 48 days old — outside the 30-day refund window → DENIED */
const ORDER_OUTSIDE_WINDOW = '10000000-0000-0000-0000-000000001002'

/** Syntactically valid UUID that does not exist in the database → 404 */
const UNKNOWN_CUSTOMER = '99999999-9999-9999-9999-999999999999'

// ---------------------------------------------------------------------------
// Scenario definitions
// ---------------------------------------------------------------------------

export const TEST_SCENARIOS: TestScenario[] = [
  {
    label: 'Approved refund',
    description: 'Valid order within the 30-day window — policy returns APPROVED',
    mode: 'structured',
    form: {
      customerId: ALICE_ID,
      orderId: ORDER_WITHIN_WINDOW,
      requestedAmount: '79.99',
      reason: 'DAMAGED_ITEM',
    },
    clearResult: true,
  },
  {
    label: 'Denied refund',
    description: 'Order is 48 days old — policy returns DENIED (outside window)',
    mode: 'structured',
    form: {
      customerId: ALICE_ID,
      orderId: ORDER_OUTSIDE_WINDOW,
      requestedAmount: '49.99',
      reason: 'OTHER',
    },
    clearResult: true,
  },
  {
    label: 'AI — damaged item',
    description: 'Natural-language message with damage reason and amount — AI extraction + policy decision',
    mode: 'ai',
    form: {
      customerId: ALICE_ID,
      orderId: ORDER_WITHIN_WINDOW,
      message:
        'My wireless keyboard arrived with several broken keys — it is completely unusable. ' +
        'I paid $79.99 and would like a full refund please.',
    },
    clearResult: true,
  },
  {
    label: 'Invalid amount',
    description: 'Amount of 0 — backend returns 422 validation error',
    mode: 'structured',
    form: {
      customerId: ALICE_ID,
      orderId: ORDER_WITHIN_WINDOW,
      requestedAmount: '0',
      reason: 'OTHER',
    },
    clearResult: true,
  },
  {
    label: 'Unknown customer',
    description: 'Valid UUID that does not exist — backend returns 404',
    mode: 'structured',
    form: {
      customerId: UNKNOWN_CUSTOMER,
      orderId: ORDER_WITHIN_WINDOW,
      requestedAmount: '49.99',
      reason: 'OTHER',
    },
    clearResult: true,
  },
  {
    label: 'Validation error',
    description: 'All fields empty — backend returns 422 for missing required fields',
    mode: 'structured',
    form: {
      customerId: '',
      orderId: '',
      requestedAmount: '',
      reason: 'OTHER',
    },
    clearResult: true,
  },
  {
    label: 'Clear form',
    description: 'Reset the form to its initial state',
    form: {
      customerId: '',
      orderId: '',
      requestedAmount: '',
      reason: 'OTHER',
      message: '',
    },
    clearResult: true,
  },
]
