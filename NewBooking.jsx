import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, fieldErrors } from "../api.js";
import { useAuth } from "../auth.jsx";
import Field from "../components/Field.jsx";
import SlotPicker from "../components/SlotPicker.jsx";
import { QUANTITIES, formatDate, formatWindow, money, quantityLabel } from "../format.js";

const STEPS = ["Your details", "Collection date", "Review & confirm"];

export default function NewBooking() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({
    customer_name: [user.first_name, user.last_name].filter(Boolean).join(" "),
    customer_email: user.email || "",
    customer_phone: "",
    address_line: "",
    suburb: "",
    postcode: "",
    waste_type: "",
    quantity: "SMALL",
    special_instructions: "",
  });
  const [area, setArea] = useState(null); // service-area check result
  const [wasteTypes, setWasteTypes] = useState([]);
  const [availability, setAvailability] = useState(null);
  const [slotId, setSlotId] = useState(null);
  const [quote, setQuote] = useState(null);
  const [acceptFee, setAcceptFee] = useState(false);
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const set = (name) => (e) => setForm((f) => ({ ...f, [name]: e.target.value }));

  // Service-area check + supported waste types whenever a full postcode is entered.
  useEffect(() => {
    if (!/^\d{4}$/.test(form.postcode)) {
      setArea(null);
      return;
    }
    let cancelled = false;
    Promise.all([
      api("/service-areas/check/", { params: { postcode: form.postcode } }),
      api("/waste-types/", { params: { postcode: form.postcode } }),
    ]).then(([check, types]) => {
      if (cancelled) return;
      setArea(check);
      setWasteTypes(types);
      if (check.eligible) setForm((f) => ({ ...f, suburb: f.suburb || check.suburb }));
      if (!types.some((t) => t.code === form.waste_type)) setForm((f) => ({ ...f, waste_type: "" }));
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.postcode]);

  const selectedType = wasteTypes.find((t) => t.code === form.waste_type);
  const selectedSlot = availability?.slots.find((s) => s.id === slotId);

  function validateDetails() {
    const e = {};
    if (!form.customer_name.trim()) e.customer_name = "Enter your name.";
    if (!/^\S+@\S+\.\S+$/.test(form.customer_email)) e.customer_email = "Enter a valid email address.";
    if (!/^\+?[\d\s()-]{8,20}$/.test(form.customer_phone)) e.customer_phone = "Enter a valid phone number.";
    if (!form.address_line.trim()) e.address_line = "Enter the collection address.";
    if (!/^\d{4}$/.test(form.postcode)) e.postcode = "Enter a 4-digit postcode.";
    else if (area && !area.eligible) e.postcode = "Sorry, this postcode is outside our collection area.";
    if (!form.waste_type) e.waste_type = "Choose what you're recycling.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function goToDates(e) {
    e.preventDefault();
    if (!validateDetails()) return;
    setBusy(true);
    setError("");
    try {
      const [avail, q] = await Promise.all([
        api("/availability/", { params: { postcode: form.postcode, waste_type: form.waste_type } }),
        api("/bookings/quote/", { method: "POST", body: { waste_type: form.waste_type, quantity: form.quantity } }),
      ]);
      setAvailability(avail);
      setQuote(q);
      if (!avail.slots.some((s) => s.id === slotId)) setSlotId(null);
      setStep(1);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    setBusy(true);
    setError("");
    try {
      const booking = await api("/bookings/", {
        method: "POST",
        body: {
          ...form,
          slot_id: slotId,
          accept_fee: acceptFee,
          // Demo payment token. A real deployment obtains this from the payment provider's widget.
          payment_token: quote?.chargeable ? "tok_demo" : "",
        },
      });
      navigate(`/bookings/${booking.booking_reference}`, { state: { justBooked: true } });
    } catch (err) {
      if (err instanceof ApiError && err.data.code === "slot_unavailable") {
        setError(err.message);
        const avail = await api("/availability/", {
          params: { postcode: form.postcode, waste_type: form.waste_type },
        });
        setAvailability(avail);
        setSlotId(null);
        setStep(1);
      } else if (err instanceof ApiError && err.data.code === "not_eligible") {
        navigate(`/bookings/${err.data.booking_reference}`);
      } else {
        const fe = fieldErrors(err);
        if (Object.keys(fe).length) {
          setErrors(fe);
          setStep(0);
        }
        setError(err.message);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Book a recycling collection</h1>
          <p className="muted">Standard recycling collections are free. Special and bulky items incur a fee.</p>
        </div>
      </div>

      <ol className="stepper">
        {STEPS.map((label, i) => (
          <li key={label} className={i === step ? "is-current" : i < step ? "is-done" : ""}>
            <span className="step-num">{i + 1}</span>
            {label}
          </li>
        ))}
      </ol>

      {error && <p className="alert alert-error">{error}</p>}

      {step === 0 && (
        <form className="card form-card" onSubmit={goToDates} noValidate>
          <h2>Contact details</h2>
          <div className="grid-2">
            <Field label="Full name" id="customer_name" error={errors.customer_name}>
              <input id="customer_name" autoComplete="name" value={form.customer_name} onChange={set("customer_name")} />
            </Field>
            <Field label="Phone" id="customer_phone" error={errors.customer_phone}>
              <input
                id="customer_phone"
                type="tel"
                autoComplete="tel"
                placeholder="04xx xxx xxx"
                value={form.customer_phone}
                onChange={set("customer_phone")}
              />
            </Field>
          </div>
          <Field label="Email" id="customer_email" error={errors.customer_email} hint="We'll send your confirmation here.">
            <input
              id="customer_email"
              type="email"
              autoComplete="email"
              value={form.customer_email}
              onChange={set("customer_email")}
            />
          </Field>

          <h2>Collection address</h2>
          <Field label="Street address" id="address_line" error={errors.address_line}>
            <input
              id="address_line"
              autoComplete="street-address"
              value={form.address_line}
              onChange={set("address_line")}
            />
          </Field>
          <div className="grid-2">
            <Field
              label="Postcode"
              id="postcode"
              error={errors.postcode}
              hint={area?.eligible ? `✓ Serviced by ${area.provider.name}` : undefined}
            >
              <input
                id="postcode"
                inputMode="numeric"
                maxLength={4}
                autoComplete="postal-code"
                value={form.postcode}
                onChange={set("postcode")}
              />
            </Field>
            <Field label="Suburb" id="suburb" error={errors.suburb}>
              <input id="suburb" autoComplete="address-level2" value={form.suburb} onChange={set("suburb")} />
            </Field>
          </div>
          {area && !area.eligible && (
            <p className="alert alert-warn">
              Postcode {form.postcode} is outside the recycling collection service area, so we can't book a collection
              there.
            </p>
          )}

          <h2>What are you recycling?</h2>
          {!area?.eligible ? (
            <p className="muted">Enter a postcode in our service area to see what can be collected.</p>
          ) : (
            <div className={`choice-grid ${errors.waste_type ? "has-error" : ""}`} role="radiogroup">
              {wasteTypes.map((t) => (
                <label key={t.code} className={`choice ${form.waste_type === t.code ? "is-selected" : ""}`}>
                  <input
                    type="radio"
                    name="waste_type"
                    value={t.code}
                    checked={form.waste_type === t.code}
                    onChange={set("waste_type")}
                  />
                  <span className="choice-title">
                    {t.name}
                    <span className={`tag ${t.is_special ? "tag-fee" : "tag-free"}`}>
                      {t.is_special ? `${money(t.base_fee)}` : "Free"}
                    </span>
                  </span>
                  <span className="choice-body">{t.accepted_items}</span>
                </label>
              ))}
            </div>
          )}
          {errors.waste_type && <p className="error-text">{errors.waste_type}</p>}

          <h2>Estimated quantity</h2>
          <div className="segmented" role="radiogroup">
            {QUANTITIES.map((q) => (
              <label key={q.value} className={form.quantity === q.value ? "is-selected" : ""}>
                <input
                  type="radio"
                  name="quantity"
                  value={q.value}
                  checked={form.quantity === q.value}
                  onChange={set("quantity")}
                />
                <strong>{q.label}</strong>
                <span>{q.hint}</span>
              </label>
            ))}
          </div>

          <Field
            label="Instructions for the collection crew (optional)"
            id="special_instructions"
            error={errors.special_instructions}
          >
            <textarea
              id="special_instructions"
              rows={3}
              maxLength={500}
              placeholder="e.g. Boxes are beside the driveway gate"
              value={form.special_instructions}
              onChange={set("special_instructions")}
            />
          </Field>

          <div className="actions">
            <button className="btn btn-primary" disabled={busy}>
              {busy ? "Checking availability…" : "Choose a date"}
            </button>
          </div>
        </form>
      )}

      {step === 1 && availability && (
        <div className="card form-card">
          <h2>Choose a collection date</h2>
          <p className="muted">
            Collections in {availability.suburb} are made by {availability.provider.name}. Have your recyclables at the
            kerb before the window starts.
          </p>
          <SlotPicker slots={availability.slots} value={slotId} onChange={setSlotId} />
          <div className="actions">
            <button className="btn" onClick={() => setStep(0)}>
              Back
            </button>
            <button className="btn btn-primary" disabled={!slotId} onClick={() => setStep(2)}>
              Review booking
            </button>
          </div>
        </div>
      )}

      {step === 2 && selectedSlot && (
        <div className="card form-card">
          <h2>Review your booking</h2>
          <dl className="summary">
            <dt>Collection</dt>
            <dd>
              {formatDate(selectedSlot.date)}
              <br />
              {formatWindow(selectedSlot.start_time, selectedSlot.end_time)}
            </dd>
            <dt>Address</dt>
            <dd>
              {form.address_line}, {form.suburb} {form.postcode}
            </dd>
            <dt>Waste type</dt>
            <dd>{selectedType?.name}</dd>
            <dt>Quantity</dt>
            <dd>{quantityLabel(form.quantity)}</dd>
            {form.special_instructions && (
              <>
                <dt>Instructions</dt>
                <dd>{form.special_instructions}</dd>
              </>
            )}
            <dt>Contact</dt>
            <dd>
              {form.customer_name} · {form.customer_phone} · {form.customer_email}
            </dd>
          </dl>

          {quote?.chargeable ? (
            <div className="fee-box">
              <h3>Fee for this collection</h3>
              <table className="fee-table">
                <tbody>
                  {quote.breakdown.map((line) => (
                    <tr key={line.item}>
                      <td>{line.item}</td>
                      <td>{money(line.amount)}</td>
                    </tr>
                  ))}
                  <tr className="total">
                    <td>Total (AUD)</td>
                    <td>{money(quote.fee)}</td>
                  </tr>
                </tbody>
              </table>
              <label className="check">
                <input type="checkbox" checked={acceptFee} onChange={(e) => setAcceptFee(e.target.checked)} />I accept
                the {money(quote.fee)} fee. It's refunded if I cancel at least 24 hours before collection.
              </label>
              <p className="hint">Demo mode: payment is simulated and no card details are collected.</p>
            </div>
          ) : (
            <p className="alert alert-ok">This is a standard recycling collection, so there's no charge.</p>
          )}

          <div className="actions">
            <button className="btn" onClick={() => setStep(1)} disabled={busy}>
              Back
            </button>
            <button
              className="btn btn-primary"
              onClick={confirm}
              disabled={busy || (quote?.chargeable && !acceptFee)}
            >
              {busy ? "Confirming…" : quote?.chargeable ? `Pay ${money(quote.fee)} and confirm` : "Confirm booking"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
