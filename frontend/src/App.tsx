import { useState } from 'react'
import { submitRefund, submitAIRefund, getRefunds } from './api/client'
import type { ApiError, RefundDecision, RefundReason, RefundRequestResponse, RefundSummaryResponse } from './api/types'

// ---------------------------------------------------------------------------
// Dev-only import — guarded by import.meta.env.DEV at runtime.
// Vite's tree-shaker removes this entire branch in production builds.
// ---------------------------------------------------------------------------
import { TEST_SCENARIOS } from './testScenarios'
import type { TestScenario } from './testScenarios'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SubmissionMode = 'structured' | 'ai'
type AppView = 'refund' | 'dashboard'

interface FormState {
  customerId: string
  orderId: string
  // Structured-mode fields
  requestedAmount: string
  reason: RefundReason
  // AI-mode field
  message: string
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const INITIAL_FORM: FormState = {
  customerId: '',
  orderId: '',
  requestedAmount: '',
  reason: 'OTHER',
  message: '',
}

const REFUND_REASONS: { value: RefundReason; label: string }[] = [
  { value: 'DAMAGED_ITEM', label: 'Damaged item' },
  { value: 'INCORRECT_ITEM', label: 'Incorrect item received' },
  { value: 'OTHER', label: 'Other' },
]

// Maps backend enum values to human-readable labels for display in results.
const REASON_LABELS: Record<string, string> = {
  DAMAGED_ITEM: 'Damaged item',
  INCORRECT_ITEM: 'Incorrect item received',
  OTHER: 'Other',
}

const DECISION_LABELS: Record<RefundDecision, string> = {
  APPROVED: 'Approved',
  DENIED: 'Denied',
  ESCALATED: 'Escalated for review',
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

function App() {
  const [view, setView] = useState<AppView>('refund')
  const [mode, setMode] = useState<SubmissionMode>('structured')
  const [form, setForm] = useState<FormState>(INITIAL_FORM)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RefundRequestResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeScenario, setActiveScenario] = useState<number | null>(null)

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  function handleModeChange(newMode: SubmissionMode) {
    setMode(newMode)
    setResult(null)
    setError(null)
  }

  function handleFieldChange(
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
  ) {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
  }

  function applyScenario(scenario: TestScenario, index: number) {
    // Switch mode if the scenario specifies one
    if (scenario.mode !== undefined) {
      setMode(scenario.mode)
    }
    // Merge the scenario's form patch over the current form state
    setForm((prev) => ({ ...prev, ...scenario.form }))
    if (scenario.clearResult) {
      setResult(null)
      setError(null)
    }
    setActiveScenario(index)
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setLoading(true)
    setResult(null)
    setError(null)

    try {
      let response: RefundRequestResponse

      if (mode === 'structured') {
        response = await submitRefund({
          customer_id: form.customerId.trim(),
          order_id: form.orderId.trim(),
          requested_amount: form.requestedAmount.trim(),
          reason: form.reason,
        })
      } else {
        response = await submitAIRefund({
          customer_id: form.customerId.trim(),
          order_id: form.orderId.trim(),
          message: form.message.trim(),
        })
      }

      setResult(response)
    } catch (err) {
      const apiError = err as ApiError
      setError(apiError.message ?? 'An unexpected error occurred.')
    } finally {
      setLoading(false)
    }
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="page">
      <header className="page-header">
        <h1>Worknoon Refund System</h1>
        <p className="page-subtitle">Submit a refund request for a customer order.</p>
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Top-level navigation: Refund Form ↔ Admin Dashboard                 */}
      {/* ------------------------------------------------------------------ */}
      <nav className="app-nav" aria-label="Application sections">
        <button
          type="button"
          className={`app-nav__tab${view === 'refund' ? ' app-nav__tab--active' : ''}`}
          aria-current={view === 'refund' ? 'page' : undefined}
          onClick={() => setView('refund')}
        >
          Refund Request
        </button>
        <button
          type="button"
          className={`app-nav__tab${view === 'dashboard' ? ' app-nav__tab--active' : ''}`}
          aria-current={view === 'dashboard' ? 'page' : undefined}
          onClick={() => setView('dashboard')}
        >
          Admin Dashboard
        </button>
      </nav>

      <main className="page-main">

        {/* ---------------------------------------------------------------- */}
        {/* Admin Dashboard view                                              */}
        {/* ---------------------------------------------------------------- */}
        {view === 'dashboard' && <AdminDashboard />}

        {/* ---------------------------------------------------------------- */}
        {/* Refund form view                                                  */}
        {/* ---------------------------------------------------------------- */}
        {view === 'refund' && (
          <>
        {/* ---------------------------------------------------------------- */}
        {/* DEV-ONLY: Test scenario selector                                  */}
        {/* Vite strips this entire block in production (import.meta.env.DEV  */}
        {/* is false in built output).                                        */}
        {/* ---------------------------------------------------------------- */}
        {import.meta.env.DEV && (
          <DevScenarioPanel
            activeScenario={activeScenario}
            onSelect={applyScenario}
          />
        )}

        {/* ---------------------------------------------------------------- */}
        {/* Mode tabs                                                         */}
        {/* ---------------------------------------------------------------- */}
        <div className="mode-tabs" role="group" aria-label="Submission mode">
          <button
            type="button"
            className={`mode-tab${mode === 'structured' ? ' mode-tab--active' : ''}`}
            aria-pressed={mode === 'structured'}
            onClick={() => handleModeChange('structured')}
          >
            Normal refund
          </button>
          <button
            type="button"
            className={`mode-tab${mode === 'ai' ? ' mode-tab--active' : ''}`}
            aria-pressed={mode === 'ai'}
            onClick={() => handleModeChange('ai')}
          >
            AI-assisted refund
          </button>
        </div>

        {mode === 'ai' && (
          <p className="mode-description">
            Describe the issue in natural language. Gemini will extract the reason
            and amount; the refund policy engine makes the final decision.
          </p>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* Form                                                              */}
        {/* ---------------------------------------------------------------- */}
        <form className="refund-form" onSubmit={handleSubmit} noValidate>
          {/* Common fields */}
          <div className="field-group">
            <div className="field">
              <label htmlFor="customerId" className="field-label">
                Customer ID <span aria-hidden="true">*</span>
              </label>
              <input
                id="customerId"
                name="customerId"
                type="text"
                className="field-input"
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                value={form.customerId}
                onChange={handleFieldChange}
                required
                disabled={loading}
                autoComplete="off"
                spellCheck={false}
              />
            </div>

            <div className="field">
              <label htmlFor="orderId" className="field-label">
                Order ID <span aria-hidden="true">*</span>
              </label>
              <input
                id="orderId"
                name="orderId"
                type="text"
                className="field-input"
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                value={form.orderId}
                onChange={handleFieldChange}
                required
                disabled={loading}
                autoComplete="off"
                spellCheck={false}
              />
            </div>
          </div>

          {/* Normal refund fields */}
          {mode === 'structured' && (
            <div className="field-group">
              <div className="field">
                <label htmlFor="requestedAmount" className="field-label">
                  Requested amount <span aria-hidden="true">*</span>
                </label>
                <input
                  id="requestedAmount"
                  name="requestedAmount"
                  type="text"
                  inputMode="decimal"
                  className="field-input"
                  placeholder="49.99"
                  value={form.requestedAmount}
                  onChange={handleFieldChange}
                  required
                  disabled={loading}
                />
              </div>

              <div className="field">
                <label htmlFor="reason" className="field-label">
                  Reason <span aria-hidden="true">*</span>
                </label>
                <select
                  id="reason"
                  name="reason"
                  className="field-input field-select"
                  value={form.reason}
                  onChange={handleFieldChange}
                  required
                  disabled={loading}
                >
                  {REFUND_REASONS.map(({ value, label }) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {/* AI-assisted refund field */}
          {mode === 'ai' && (
            <div className="field">
              <label htmlFor="message" className="field-label">
                Customer message <span aria-hidden="true">*</span>
              </label>
              <textarea
                id="message"
                name="message"
                className="field-input field-textarea"
                placeholder="Describe the issue and the amount you are requesting, e.g. 'My item arrived with a cracked screen. I paid $49.99 and would like a full refund.'"
                rows={5}
                value={form.message}
                onChange={handleFieldChange}
                required
                disabled={loading}
              />
            </div>
          )}

          <div className="form-actions">
            <button
              type="submit"
              className="btn-submit"
              disabled={loading}
              aria-busy={loading}
            >
              {loading ? 'Submitting…' : 'Submit refund request'}
            </button>
          </div>
        </form>

        {/* ---------------------------------------------------------------- */}
        {/* Error                                                             */}
        {/* ---------------------------------------------------------------- */}
        {error !== null && (
          <div className="result-panel result-panel--error" role="alert">
            <p className="result-panel__heading">Request failed</p>
            <p className="result-panel__message">{error}</p>
          </div>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* Result                                                            */}
        {/* ---------------------------------------------------------------- */}
        {result !== null && (
          <RefundResult result={result} mode={mode} />
        )}
          </>
        )}
      </main>
    </div>
  )
}

// ---------------------------------------------------------------------------
// DevScenarioPanel — rendered only when import.meta.env.DEV is true
// ---------------------------------------------------------------------------

interface DevScenarioPanelProps {
  activeScenario: number | null
  onSelect: (scenario: TestScenario, index: number) => void
}

function DevScenarioPanel({ activeScenario, onSelect }: DevScenarioPanelProps) {
  return (
    <aside className="dev-panel" aria-label="Test scenarios (development only)">
      <p className="dev-panel__heading">
        <span className="dev-panel__badge">DEV</span>
        Test scenarios
      </p>
      <p className="dev-panel__hint">
        Select a scenario to populate the form. The request is still submitted
        to the real backend — no responses are mocked.
      </p>
      <div className="dev-panel__scenarios">
        {TEST_SCENARIOS.map((scenario, i) => (
          <button
            key={scenario.label}
            type="button"
            className={`dev-scenario-btn${activeScenario === i ? ' dev-scenario-btn--active' : ''}`}
            onClick={() => onSelect(scenario, i)}
            title={scenario.description}
          >
            <span className="dev-scenario-btn__label">{scenario.label}</span>
            <span className="dev-scenario-btn__desc">{scenario.description}</span>
          </button>
        ))}
      </div>
    </aside>
  )
}

// ---------------------------------------------------------------------------
// RefundResult sub-component
// ---------------------------------------------------------------------------

interface RefundResultProps {
  result: RefundRequestResponse
  mode: SubmissionMode
}

function RefundResult({ result, mode }: RefundResultProps) {
  const decision = result.decision as RefundDecision | null
  const decisionLabel = decision ? DECISION_LABELS[decision] : 'Pending'
  const reasonLabel = REASON_LABELS[result.reason] ?? result.reason

  const panelModifier =
    decision === 'APPROVED'
      ? 'approved'
      : decision === 'DENIED'
        ? 'denied'
        : decision === 'ESCALATED'
          ? 'escalated'
          : 'pending'

  return (
    <section
      className={`result-panel result-panel--${panelModifier}`}
      aria-live="polite"
    >
      <p className="result-panel__heading">Refund decision</p>

      <div className={`decision-badge decision-badge--${panelModifier}`}>
        {decisionLabel}
      </div>

      {result.decision_reason && (
        <p className="result-panel__reason">{result.decision_reason}</p>
      )}

      <dl className="result-details">
        <div className="result-details__row">
          <dt>Reference ID</dt>
          <dd><code>{result.id}</code></dd>
        </div>
        {mode === 'ai' ? (
          <>
            <div className="result-details__row">
              <dt>AI-extracted reason</dt>
              <dd>{reasonLabel}</dd>
            </div>
            <div className="result-details__row">
              <dt>AI-extracted amount</dt>
              <dd>${result.requested_amount}</dd>
            </div>
            <div className="result-details__row">
              <dt>Processed via</dt>
              <dd>AI-assisted (Gemini extracted reason &amp; amount)</dd>
            </div>
          </>
        ) : (
          <>
            <div className="result-details__row">
              <dt>Reason</dt>
              <dd>{reasonLabel}</dd>
            </div>
            <div className="result-details__row">
              <dt>Requested amount</dt>
              <dd>${result.requested_amount}</dd>
            </div>
          </>
        )}
        <div className="result-details__row">
          <dt>Submitted</dt>
          <dd>{new Date(result.created_at).toLocaleString()}</dd>
        </div>
      </dl>
    </section>
  )
}

export default App

// ---------------------------------------------------------------------------
// AdminDashboard component
// ---------------------------------------------------------------------------

const DECISION_BADGE_CLASS: Record<string, string> = {
  APPROVED: 'decision-badge--approved',
  DENIED: 'decision-badge--denied',
  ESCALATED: 'decision-badge--escalated',
}

const REASON_LABELS_DASHBOARD: Record<string, string> = {
  DAMAGED_ITEM: 'Damaged item',
  INCORRECT_ITEM: 'Incorrect item',
  OTHER: 'Other',
}

function AdminDashboard() {
  const [records, setRecords] = useState<RefundSummaryResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastFetched, setLastFetched] = useState<Date | null>(null)

  async function fetchRecords() {
    setLoading(true)
    setError(null)
    try {
      const data = await getRefunds(50)
      setRecords(data)
      setLastFetched(new Date())
    } catch (err) {
      const apiError = err as ApiError
      setError(apiError.message ?? 'Failed to load refund requests.')
    } finally {
      setLoading(false)
    }
  }

  // Fetch on first render
  useState(() => {
    void fetchRecords()
  })

  return (
    <section className="dashboard" aria-label="Admin refund dashboard">
      <div className="dashboard__header">
        <div>
          <h2 className="dashboard__title">Recent Refund Requests</h2>
          {lastFetched && (
            <p className="dashboard__meta">
              Last updated: {lastFetched.toLocaleTimeString()}
            </p>
          )}
        </div>
        <button
          type="button"
          className="btn-refresh"
          onClick={fetchRecords}
          disabled={loading}
          aria-busy={loading}
        >
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div className="result-panel result-panel--error" role="alert">
          <p className="result-panel__heading">Failed to load</p>
          <p className="result-panel__message">{error}</p>
        </div>
      )}

      {!error && records.length === 0 && !loading && (
        <p className="dashboard__empty">
          No refund requests found. Submit one using the Refund Request tab.
        </p>
      )}

      {records.length > 0 && (
        <div className="dashboard__table-wrapper">
          <table className="dashboard-table" aria-label="Refund requests">
            <thead>
              <tr>
                <th scope="col">Submitted</th>
                <th scope="col">Customer</th>
                <th scope="col">Order</th>
                <th scope="col">Amount</th>
                <th scope="col">Reason</th>
                <th scope="col">Decision</th>
                <th scope="col">Audit note</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r) => {
                const decisionKey = r.decision ?? 'PENDING'
                const badgeClass = DECISION_BADGE_CLASS[decisionKey] ?? ''
                return (
                  <tr key={r.id}>
                    <td className="dashboard-table__date">
                      {new Date(r.created_at).toLocaleString()}
                    </td>
                    <td>
                      <span className="dashboard-table__name">{r.customer_name}</span>
                    </td>
                    <td>
                      <code className="dashboard-table__order">{r.order_number}</code>
                    </td>
                    <td className="dashboard-table__amount">
                      ${r.requested_amount}
                    </td>
                    <td>{REASON_LABELS_DASHBOARD[r.reason] ?? r.reason}</td>
                    <td>
                      <span className={`decision-badge ${badgeClass}`}>
                        {r.decision ?? 'Pending'}
                      </span>
                    </td>
                    <td className="dashboard-table__reason">
                      {r.decision_reason ?? '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
