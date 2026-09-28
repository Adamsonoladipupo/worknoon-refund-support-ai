/**
 * TypeScript types derived from the backend Pydantic schemas.
 *
 * Source of truth: backend/app/schemas/refund.py
 * Do not add fields that the backend does not return.
 * Do not hardcode policy logic here — the backend is the authority.
 */

/**
 * Refund reason options — mirrors app.policies.refund_policy.RefundReason.
 * Must be sent as-is; the backend validates against this enum.
 */
export type RefundReason = 'DAMAGED_ITEM' | 'INCORRECT_ITEM' | 'OTHER'

export type RefundDecision = 'APPROVED' | 'DENIED' | 'ESCALATED'

/**
 * POST /api/refunds — structured refund request.
 * Source: app.schemas.refund.RefundRequestCreate
 */
export interface RefundRequestCreate {
  customer_id: string
  order_id: string
  requested_amount: string
  reason: RefundReason
}

/**
 * POST /api/refunds/ai — natural-language refund request.
 * Source: app.schemas.refund.AIRefundRequestCreate
 */
export interface AIRefundRequestCreate {
  customer_id: string
  order_id: string
  message: string
}

/**
 * Both POST /api/refunds and POST /api/refunds/ai return this shape on 201.
 * Source: app.schemas.refund.RefundRequestResponse
 *
 * Note: the AI endpoint does NOT return AI analysis fields (reason, summary,
 * confidence, etc.) — those are internal to the backend workflow. Both
 * endpoints return the same persisted refund record.
 */
export interface RefundRequestResponse {
  id: string
  customer_id: string
  order_id: string
  reason: string
  requested_amount: string
  decision: RefundDecision | null
  decision_reason: string | null
  created_at: string
  updated_at: string
}

/**
 * GET /api/refunds — admin dashboard list item.
 * Source: app.schemas.refund.RefundSummaryResponse
 */
export interface RefundSummaryResponse {
  id: string
  customer_id: string
  customer_name: string
  order_id: string
  order_number: string
  reason: string
  requested_amount: string
  decision: RefundDecision | null
  decision_reason: string | null
  created_at: string
}

export interface FastAPIValidationErrorItem {
  loc: (string | number)[]
  msg: string
  type: string
}

export interface FastAPIErrorBody {
  detail: string | FastAPIValidationErrorItem[]
}

export interface ApiError {
  status: number
  message: string
}
