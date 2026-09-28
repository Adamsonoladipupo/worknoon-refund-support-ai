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

/**
 * Possible refund decisions returned by the policy engine.
 * These are the only values the backend ever writes to the decision field.
 */
export type RefundDecision = 'APPROVED' | 'DENIED' | 'ESCALATED'

/**
 * POST /api/refunds — structured refund request.
 * Source: app.schemas.refund.RefundRequestCreate
 */
export interface RefundRequestCreate {
  customer_id: string   // UUID string
  order_id: string      // UUID string
  requested_amount: string  // Decimal-safe: send as string, e.g. "49.99"
  reason: RefundReason
}

/**
 * POST /api/refunds/ai — natural-language refund request.
 * Source: app.schemas.refund.AIRefundRequestCreate
 */
export interface AIRefundRequestCreate {
  customer_id: string   // UUID string
  order_id: string      // UUID string
  message: string       // Non-empty; validated by backend (strips whitespace)
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
  id: string                      // UUID
  customer_id: string             // UUID
  order_id: string                // UUID
  reason: string                  // Value of RefundReason enum as stored
  requested_amount: string        // Decimal string, e.g. "49.99"
  decision: RefundDecision | null // null means pending (not yet evaluated)
  decision_reason: string | null
  created_at: string              // ISO 8601 datetime
  updated_at: string              // ISO 8601 datetime
}

/**
 * GET /api/refunds — admin dashboard list item.
 * Source: app.schemas.refund.RefundSummaryResponse
 */
export interface RefundSummaryResponse {
  id: string                      // UUID
  customer_id: string             // UUID
  customer_name: string           // Joined from Customer.name
  order_id: string                // UUID
  order_number: string            // Joined from Order.order_number
  reason: string                  // RefundReason value
  requested_amount: string        // Decimal string
  decision: RefundDecision | null
  decision_reason: string | null
  created_at: string              // ISO 8601 datetime
}

/**
 * FastAPI validation error detail item (422 responses).
 */
export interface FastAPIValidationErrorItem {
  loc: (string | number)[]
  msg: string
  type: string
}

/**
 * FastAPI HTTP error body (404, 422, 502, 503, etc.).
 * `detail` is a string for HTTP exceptions and an array for Pydantic 422s.
 */
export interface FastAPIErrorBody {
  detail: string | FastAPIValidationErrorItem[]
}

/**
 * Normalized API error returned from client functions.
 * Callers always get a human-readable message string.
 */
export interface ApiError {
  status: number
  message: string
}
