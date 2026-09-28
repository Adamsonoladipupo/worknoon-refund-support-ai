/**
 * API client for the Worknoon Refund System backend.
 *
 * Endpoints consumed:
 *   POST /api/refunds      — structured refund (RefundRequestCreate)
 *   POST /api/refunds/ai   — AI-assisted refund (AIRefundRequestCreate)
 *
 * Both return RefundRequestResponse on 201.
 * Errors are normalized to ApiError with a human-readable message.
 */

import type {
  AIRefundRequestCreate,
  ApiError,
  FastAPIErrorBody,
  FastAPIValidationErrorItem,
  RefundRequestCreate,
  RefundRequestResponse,
  RefundSummaryResponse,
} from './types'

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

/**
 * Convert a FastAPI error body to a user-readable string.
 * Handles both string `detail` (HTTP exceptions) and array `detail`
 * (Pydantic 422 validation errors).
 */
function extractErrorMessage(body: FastAPIErrorBody): string {
  if (typeof body.detail === 'string') {
    return body.detail
  }

  if (Array.isArray(body.detail) && body.detail.length > 0) {
    return body.detail
      .map((item: FastAPIValidationErrorItem) => {
        const field = item.loc.slice(1).join('.')
        return field ? `${field}: ${item.msg}` : item.msg
      })
      .join('; ')
  }

  return 'An unexpected error occurred.'
}

/**
 * Attempt to parse the response body as JSON and extract a message.
 * Falls back to a generic message if parsing fails or the body is empty.
 */
async function parseErrorResponse(response: Response): Promise<ApiError> {
  let message = `Request failed with status ${response.status}.`

  try {
    const text = await response.text()
    if (text) {
      const body = JSON.parse(text) as FastAPIErrorBody
      message = extractErrorMessage(body)
    }
  } catch {
    // JSON parse failed — use the default status-based message.
  }

  // Provide friendlier fallbacks for specific well-known status codes that
  // may arrive before JSON is available (e.g. 502/503 from a proxy).
  if (!message || message === `Request failed with status ${response.status}.`) {
    if (response.status === 502) {
      message = 'The AI analysis service is temporarily unavailable. Please try again later.'
    } else if (response.status === 503) {
      message = 'The AI service is not configured on the server. Contact support.'
    }
  }

  return { status: response.status, message }
}

async function getJson<TResponse>(path: string): Promise<TResponse> {
  let response: Response

  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    })
  } catch (networkError) {
    const message =
      networkError instanceof TypeError
        ? `Could not reach the server at ${BASE_URL}. Make sure the backend is running.`
        : 'An unexpected network error occurred.'
    const err: ApiError = { status: 0, message }
    throw err
  }

  if (!response.ok) {
    const err = await parseErrorResponse(response)
    throw err
  }

  return (await response.json()) as TResponse
}

async function postJson<TBody, TResponse>(
  path: string,
  body: TBody,
): Promise<TResponse> {
  let response: Response

  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (networkError) {
    // fetch() itself threw — network is down or CORS preflight failed.
    const message =
      networkError instanceof TypeError
        ? `Could not reach the server at ${BASE_URL}. Make sure the backend is running.`
        : 'An unexpected network error occurred.'
    const err: ApiError = { status: 0, message }
    throw err
  }

  if (!response.ok) {
    const err = await parseErrorResponse(response)
    throw err
  }

  return (await response.json()) as TResponse
}

/**
 * POST /api/refunds
 *
 * Submit a structured refund request.
 * Returns the created RefundRequestResponse (201) or throws ApiError.
 */
export async function submitRefund(
  body: RefundRequestCreate,
): Promise<RefundRequestResponse> {
  return postJson<RefundRequestCreate, RefundRequestResponse>('/api/refunds', body)
}

/**
 * POST /api/refunds/ai
 *
 * Submit a natural-language refund request.
 * Gemini extracts reason + amount; RefundPolicy produces the final decision.
 * Returns the created RefundRequestResponse (201) or throws ApiError.
 */
export async function submitAIRefund(
  body: AIRefundRequestCreate,
): Promise<RefundRequestResponse> {
  return postJson<AIRefundRequestCreate, RefundRequestResponse>('/api/refunds/ai', body)
}

/**
 * GET /api/refunds
 *
 * Retrieve recent refund requests for the admin/support dashboard.
 * Returns an array of RefundSummaryResponse ordered newest first.
 */
export async function getRefunds(limit = 50): Promise<RefundSummaryResponse[]> {
  return getJson<RefundSummaryResponse[]>(`/api/refunds?limit=${limit}`)
}
