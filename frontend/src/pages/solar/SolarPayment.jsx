import { useEffect, useState } from "react";
import { api, ApiError, fieldErrors } from "../../api.js";
import Field from "../../components/Field.jsx";
import { formatDateTime } from "../../format.js";
import { aud } from "./common.jsx";

// Payment section on a solar request (ORG-001). Demo only: no real card is charged.

const PAY_TONES = {
  UNPAID: "badge-pending",
  DEPOSIT: "badge-confirmed",
  PAID: "badge-collected",
  REFUNDED: "badge-cancelled",
};

export function PaymentStatus({ payment }) {
  return <span className={`badge ${PAY_TONES[payment.status] || ""}`}>{payment.status_label}</span>;
}

/** "4242424242424242" -> "4242 4242 4242 4242" */
function formatCardNumber(value) {
  return value.replace(/\D/g, "").slice(0, 19).replace(/(\d{4})(?=\d)/g, "$1 ");
}

/** "1230" -> "12/30" */
function formatExpiry(value) {
  const digits = value.replace(/\D/g, "").slice(0, 4);
  return digits.length > 2 ? `${digits.slice(0, 2)}/${digits.slice(2)}` : digits;
}

export default function SolarPayment({ request, onPaid }) {
  const { payment } = request;
  const [option, setOption] = useState(payment.options[0]?.id || "");
  const [card, setCard] = useState({ cardholder_name: request.customer_name, card_number: "", expiry: "", cvc: "" });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // When the options change (e.g. after paying the deposit), select the first one.
  useEffect(() => {
    if (!payment.options.some((o) => o.id === option)) setOption(payment.options[0]?.id || "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payment.options.map((o) => o.id).join()]);

  const chosen = payment.options.find((o) => o.id === option);

  const set = (name, format = (v) => v) => (e) => {
    setCard((c) => ({ ...c, [name]: format(e.target.value) }));
    setErrors((errs) => ({ ...errs, [name]: undefined }));
  };

  async function pay(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setErrors({});
    try {
      const updated = await api(`/solar/requests/${request.reference}/pay/`, {
        method: "POST",
        body: { option, ...card },
      });
      setCard((c) => ({ ...c, card_number: "", expiry: "", cvc: "" }));
      onPaid(updated, `Payment of ${aud(chosen.amount)} received. Thank you!`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setErrors(fieldErrors(err));
        setError("Please check your card details.");
      } else {
        setError(err.message);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <div className="row-between">
        <h2>Payment</h2>
        <PaymentStatus payment={payment} />
      </div>

      <dl className="summary">
        <dt>Quote estimate</dt>
        <dd>{aud(request.total_price)}</dd>
        <dt>Paid so far</dt>
        <dd>{aud(payment.amount_paid)}</dd>
        {request.status !== "CANCELLED" && (
          <>
            <dt>Balance due</dt>
            <dd><strong>{aud(payment.balance_due)}</strong></dd>
          </>
        )}
      </dl>

      {payment.options.length > 0 && (
        <form onSubmit={pay} noValidate className="pay-form">
          <div className="choice-grid" role="radiogroup" aria-label="How much to pay">
            {payment.options.map((o) => (
              <label key={o.id} className={`choice ${option === o.id ? "is-selected" : ""}`}>
                <input type="radio" name="pay-option" value={o.id} checked={option === o.id}
                  onChange={() => setOption(o.id)} />
                <span className="choice-title">
                  {o.label} <span className="tag tag-fee">{aud(o.amount)}</span>
                </span>
                <span className="choice-body">{o.description}</span>
              </label>
            ))}
          </div>

          <p className="alert alert-warn small demo-note">
            <strong>Demo payment:</strong> no real money is charged. Use test card <code>4242 4242 4242 4242</code>,
            any future expiry and any 3 digits. <code>4000 0000 0000 0002</code> shows a declined card.
          </p>

          {error && <p className="alert alert-error">{error}</p>}

          <Field label="Name on card" id="cardholder_name" error={errors.cardholder_name}>
            <input id="cardholder_name" autoComplete="cc-name" value={card.cardholder_name}
              onChange={set("cardholder_name")} />
          </Field>
          <Field label="Card number" id="card_number" error={errors.card_number} hint="Visa, Mastercard or American Express">
            <input id="card_number" inputMode="numeric" autoComplete="cc-number" placeholder="1234 5678 9012 3456"
              value={card.card_number} onChange={set("card_number", formatCardNumber)} />
          </Field>
          <div className="grid-2">
            <Field label="Expiry (MM/YY)" id="expiry" error={errors.expiry}>
              <input id="expiry" inputMode="numeric" autoComplete="cc-exp" placeholder="MM/YY"
                value={card.expiry} onChange={set("expiry", formatExpiry)} />
            </Field>
            <Field label="Security code" id="cvc" error={errors.cvc}>
              <input id="cvc" inputMode="numeric" autoComplete="cc-csc" placeholder="123" maxLength={4}
                value={card.cvc} onChange={set("cvc", (v) => v.replace(/\D/g, ""))} />
            </Field>
          </div>

          <button className="btn btn-primary btn-block" type="submit" disabled={busy || !chosen}>
            {busy ? "Processing…" : `Pay ${chosen ? aud(chosen.amount) : ""}`}
          </button>
        </form>
      )}

      {payment.status === "PAID" && (
        <p className="alert alert-ok">Your quote is paid in full. Nothing more to pay.</p>
      )}
      {request.status === "CANCELLED" && payment.status === "REFUNDED" && (
        <p className="alert alert-ok">This request was cancelled and your payment has been refunded.</p>
      )}

      {payment.receipts.length > 0 && (
        <>
          <h3>Receipts</h3>
          <table className="fee-table receipts">
            <tbody>
              {payment.receipts.map((p) => (
                <tr key={p.receipt_number}>
                  <td>
                    <strong>{p.kind_label}</strong>
                    <span className="muted small"> · {p.card_brand} ending {p.card_last4}</span>
                    <br />
                    <span className="muted small">{p.receipt_number} · {formatDateTime(p.created_at)}</span>
                  </td>
                  <td>{p.kind === "REFUND" ? `−${aud(p.amount)}` : aud(p.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
