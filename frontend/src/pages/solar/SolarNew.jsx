import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, fieldErrors } from "../../api.js";
import { useAuth } from "../../auth.jsx";
import Field from "../../components/Field.jsx";
import SlotPicker from "../../components/SlotPicker.jsx";
import { formatDate, formatWindow } from "../../format.js";
import { aud } from "./common.jsx";

const STEPS = ["Your property", "Site assessment", "Review & confirm"];

export default function SolarNew() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [options, setOptions] = useState(null);
  const [form, setForm] = useState({
    customer_name: [user.first_name, user.last_name].filter(Boolean).join(" "),
    customer_email: user.email || "",
    customer_phone: "",
    address_line: "",
    suburb: "",
    postcode: "",
    property_type: "house",
    storeys: "single",
    roof_type: "",
    quarterly_usage_kwh: "",
    system_size: "",
    add_ons: [],
    notes: "",
  });
  const [area, setArea] = useState(null);
  const [slots, setSlots] = useState(null);
  const [slotId, setSlotId] = useState(null);
  const [agree, setAgree] = useState(false);
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Editing a field clears its error message straight away.
  const clearError = (name) =>
    setErrors((errs) => {
      if (!errs[name]) return errs;
      const next = { ...errs };
      delete next[name];
      return next;
    });
  const choose = (name, value) => {
    setForm((f) => ({ ...f, [name]: value }));
    clearError(name);
  };
  const set = (name) => (e) => choose(name, e.target.value);
  const toggleAddOn = (id) =>
    setForm((f) => ({ ...f, add_ons: f.add_ons.includes(id) ? f.add_ons.filter((x) => x !== id) : [...f.add_ons, id] }));

  useEffect(() => {
    api("/solar/options/").then(setOptions).catch((err) => setError(err.message));
  }, []);

  // Installer and suburbs for a full postcode
  useEffect(() => {
    if (!/^\d{4}$/.test(form.postcode)) {
      setArea(null);
      return;
    }
    let cancelled = false;
    api("/solar/postcode/", { params: { postcode: form.postcode } }).then((res) => {
      if (cancelled) return;
      setArea(res);
      if (res.suburbs.length && !res.suburbs.includes(form.suburb.toUpperCase())) {
        setForm((f) => ({ ...f, suburb: res.suburbs[0] }));
      }
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.postcode]);

  // Recommended size: about 4 peak sun hours a day
  const recommended = useMemo(() => {
    const usage = Number(form.quarterly_usage_kwh);
    if (!options || !(usage > 0)) return null;
    const daily = usage / 91;
    return options.system_sizes.find((s) => daily <= s.dailyKwh) || options.system_sizes[options.system_sizes.length - 1];
  }, [form.quarterly_usage_kwh, options]);

  const pick = (list, id) => list?.find((x) => x.id === id);
  const system = pick(options?.system_sizes, form.system_size);
  const roof = pick(options?.roof_types, form.roof_type);
  const storey = pick(options?.storeys, form.storeys);
  const property = pick(options?.property_types, form.property_type);
  const addOns = (options?.add_ons || []).filter((a) => form.add_ons.includes(a.id));

  const lines = [];
  if (system) lines.push([system.name, system.price]);
  if (roof?.surcharge) lines.push([`${roof.name} roof mounting`, roof.surcharge]);
  if (storey?.surcharge) lines.push([`${storey.name} access`, storey.surcharge]);
  addOns.forEach((a) => lines.push([a.name, a.price]));
  const total = lines.reduce((sum, [, amount]) => sum + amount, 0);

  const selectedSlot = slots?.find((s) => s.id === slotId);

  function validate() {
    const e = {};
    if (form.customer_name.trim().length < 2) e.customer_name = "Enter your name.";
    if (!/^\S+@\S+\.\S+$/.test(form.customer_email)) e.customer_email = "Enter a valid email address.";
    if (!/^\+?[\d\s()-]{8,20}$/.test(form.customer_phone)) e.customer_phone = "Enter a valid phone number.";
    if (form.address_line.trim().length < 3) e.address_line = "Enter the installation address.";
    if (!/^\d{4}$/.test(form.postcode)) e.postcode = "Enter a 4-digit postcode.";
    else if (area && !area.eligible) e.postcode = "Sorry, we don't install solar in this postcode yet.";
    if (form.suburb.trim().length < 2) e.suburb = "Enter the suburb.";
    if (!(Number(form.quarterly_usage_kwh) > 0)) e.quarterly_usage_kwh = "Usage must be greater than 0 kWh.";
    if (!form.roof_type) e.roof_type = "Choose your roof type.";
    if (!form.system_size) e.system_size = "Choose a system size.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function goToAssessment(e) {
    e.preventDefault();
    if (!validate()) {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    setBusy(true);
    setError("");
    try {
      const res = await api("/solar/availability/");
      setSlots(res.slots);
      if (!res.slots.some((s) => s.id === slotId)) setSlotId(null);
      setStep(1);
      window.scrollTo({ top: 0 });
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
      const created = await api("/solar/requests/", {
        method: "POST",
        body: { ...form, quarterly_usage_kwh: Number(form.quarterly_usage_kwh), slot_id: slotId },
      });
      navigate(`/solar/${created.reference}`, { state: { justBooked: true } });
    } catch (err) {
      if (err instanceof ApiError && err.data.code === "slot_unavailable") {
        setError(err.message);
        setSlots((await api("/solar/availability/")).slots);
        setSlotId(null);
        setStep(1);
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

  if (!options) {
    return error ? <p className="alert alert-error">{error}</p> : <p className="muted">Loading…</p>;
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Request a solar installation</h1>
          <p className="muted">The site assessment is free. You only pay once you accept the installer's final quote.</p>
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
      {step === 0 && Object.keys(errors).length > 0 && (
        <p className="alert alert-error">Please fix the highlighted fields below.</p>
      )}

      {/* ---------------- Step 1: property, energy and system ---------------- */}
      {step === 0 && (
        <form className="card form-card" onSubmit={goToAssessment} noValidate>
          <h2>Contact details</h2>
          <div className="grid-2">
            <Field label="Full name" id="customer_name" error={errors.customer_name}>
              <input id="customer_name" autoComplete="name" value={form.customer_name} onChange={set("customer_name")} />
            </Field>
            <Field label="Phone" id="customer_phone" error={errors.customer_phone}>
              <input id="customer_phone" type="tel" autoComplete="tel" placeholder="04xx xxx xxx"
                value={form.customer_phone} onChange={set("customer_phone")} />
            </Field>
          </div>
          <Field label="Email" id="customer_email" error={errors.customer_email} hint="We'll send your confirmation here.">
            <input id="customer_email" type="email" autoComplete="email" value={form.customer_email} onChange={set("customer_email")} />
          </Field>

          <h2>Installation address</h2>
          <Field label="Street address" id="address_line" error={errors.address_line}>
            <input id="address_line" autoComplete="street-address" value={form.address_line} onChange={set("address_line")} />
          </Field>
          <div className="grid-2">
            <Field label="Postcode" id="postcode" error={errors.postcode}
              hint={area?.eligible ? `✓ Serviced by ${area.installer.name}` : undefined}>
              <input id="postcode" inputMode="numeric" maxLength={4} autoComplete="postal-code"
                value={form.postcode} onChange={(e) => choose("postcode", e.target.value.replace(/\D/g, ""))} />
            </Field>
            <Field label="Suburb" id="suburb" error={errors.suburb}>
              {area?.suburbs?.length ? (
                <select id="suburb" value={form.suburb} onChange={set("suburb")}>
                  {area.suburbs.map((s) => <option key={s}>{s}</option>)}
                </select>
              ) : (
                <input id="suburb" autoComplete="address-level2" value={form.suburb} onChange={set("suburb")} />
              )}
            </Field>
          </div>
          {area && !area.eligible && (
            <p className="alert alert-warn">Postcode {form.postcode} is outside the areas our installers cover.</p>
          )}

          <h2>About the property</h2>
          <div className="grid-2">
            <Field label="Property type" id="property_type">
              <select id="property_type" value={form.property_type} onChange={set("property_type")}>
                {options.property_types.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </Field>
            <Field label="Number of storeys" id="storeys">
              <select id="storeys" value={form.storeys} onChange={set("storeys")}>
                {options.storeys.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}{s.surcharge ? ` (+${aud(s.surcharge)})` : ""}</option>
                ))}
              </select>
            </Field>
          </div>

          <h2>Roof type</h2>
          <div className={`choice-grid ${errors.roof_type ? "has-error" : ""}`} role="radiogroup">
            {options.roof_types.map((r) => (
              <label key={r.id} className={`choice ${form.roof_type === r.id ? "is-selected" : ""}`}>
                <input type="radio" name="roof_type" value={r.id} checked={form.roof_type === r.id}
                  onChange={() => choose("roof_type", r.id)} />
                <span className="choice-title">
                  {r.name}
                  <span className={`tag ${r.surcharge ? "tag-fee" : "tag-free"}`}>{r.surcharge ? `+${aud(r.surcharge)}` : "No extra"}</span>
                </span>
                <span className="choice-body">{r.description}</span>
              </label>
            ))}
          </div>
          {errors.roof_type && <p className="error-text">{errors.roof_type}</p>}

          <h2>Energy use and system size</h2>
          <Field label="Average quarterly electricity usage (kWh)" id="quarterly_usage_kwh"
            error={errors.quarterly_usage_kwh} hint="You'll find this on your electricity bill.">
            <input id="quarterly_usage_kwh" type="number" min="1" placeholder="e.g. 1500"
              value={form.quarterly_usage_kwh} onChange={set("quarterly_usage_kwh")} />
          </Field>
          {recommended && (
            <p className="alert alert-ok">
              That's about {Math.round(Number(form.quarterly_usage_kwh) / 91)} kWh a day, so we recommend the{" "}
              <strong>{recommended.name}</strong>.
            </p>
          )}
          <div className={`choice-grid ${errors.system_size ? "has-error" : ""}`} role="radiogroup">
            {options.system_sizes.map((s) => (
              <label key={s.id} className={`choice ${form.system_size === s.id ? "is-selected" : ""}`}>
                <input type="radio" name="system_size" value={s.id} checked={form.system_size === s.id}
                  onChange={() => choose("system_size", s.id)} />
                <span className="choice-title">
                  {s.name}
                  <span className="tag tag-free">{aud(s.price)}</span>
                </span>
                <span className="choice-body">
                  {s.description} {s.panels} panels{recommended?.id === s.id ? " · Recommended" : ""}
                </span>
              </label>
            ))}
          </div>
          {errors.system_size && <p className="error-text">{errors.system_size}</p>}

          <h2>Optional extras</h2>
          <div className="choice-grid">
            {options.add_ons.map((a) => (
              <label key={a.id} className={`choice ${form.add_ons.includes(a.id) ? "is-selected" : ""}`}>
                <input type="checkbox" checked={form.add_ons.includes(a.id)} onChange={() => toggleAddOn(a.id)} />
                <span className="choice-title">
                  {a.name}
                  <span className="tag tag-fee">+{aud(a.price)}</span>
                </span>
                <span className="choice-body">{a.description}</span>
              </label>
            ))}
          </div>

          <Field label="Notes for the installer (optional)" id="notes" error={errors.notes}>
            <textarea id="notes" rows={3} maxLength={500} placeholder="Access details, pets, switchboard location…"
              value={form.notes} onChange={set("notes")} />
          </Field>

          <div className="actions">
            {total > 0 && <span className="muted">Estimated total <strong>{aud(total)}</strong></span>}
            <button className="btn btn-primary" disabled={busy}>
              {busy ? "Checking availability…" : "Choose assessment date"}
            </button>
          </div>
        </form>
      )}

      {/* ---------------- Step 2: site assessment slot ---------------- */}
      {step === 1 && slots && (
        <div className="card form-card">
          <h2>Choose a site assessment date</h2>
          <p className="muted">
            {area?.installer?.name} will visit to check your roof and switchboard. Someone aged 18+ needs to be home.
          </p>
          <SlotPicker slots={slots} value={slotId} onChange={setSlotId} />
          <div className="actions">
            <button className="btn" onClick={() => setStep(0)}>Back</button>
            <button className="btn btn-primary" disabled={!slotId} onClick={() => setStep(2)}>Review request</button>
          </div>
        </div>
      )}

      {/* ---------------- Step 3: review ---------------- */}
      {step === 2 && selectedSlot && (
        <div className="card form-card">
          <h2>Review your request</h2>
          <dl className="summary">
            <dt>Site assessment</dt>
            <dd>
              {formatDate(selectedSlot.date)}
              <br />
              {formatWindow(selectedSlot.start_time, selectedSlot.end_time)}
            </dd>
            <dt>Installer</dt>
            <dd>{area?.installer?.name}</dd>
            <dt>Address</dt>
            <dd>{form.address_line}, {form.suburb} {form.postcode}</dd>
            <dt>Property</dt>
            <dd>{property?.name} · {storey?.name} · {roof?.name} roof</dd>
            <dt>Quarterly usage</dt>
            <dd>{Number(form.quarterly_usage_kwh).toLocaleString()} kWh</dd>
            {form.notes && (<><dt>Notes</dt><dd>{form.notes}</dd></>)}
            <dt>Contact</dt>
            <dd>{form.customer_name} · {form.customer_phone} · {form.customer_email}</dd>
          </dl>

          <div className="fee-box">
            <h3>Quote estimate</h3>
            <table className="fee-table">
              <tbody>
                {lines.map(([item, amount]) => (
                  <tr key={item}><td>{item}</td><td>{aud(amount)}</td></tr>
                ))}
                <tr className="total"><td>Estimated total (inc. GST)</td><td>{aud(total)}</td></tr>
              </tbody>
            </table>
            <p className="hint">
              The installer confirms the final price after the assessment. Government STC rebates may reduce it.
              The site assessment is free. After booking you can pay a 10% deposit ({aud(Math.round(total * 0.1))})
              or the full amount, and you get a full refund if you cancel.
            </p>
            <label className="check">
              <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
              I own the property (or have the owner's permission) and agree to a site assessment.
            </label>
          </div>

          <div className="actions">
            <button className="btn" onClick={() => setStep(1)} disabled={busy}>Back</button>
            <button className="btn btn-primary" onClick={confirm} disabled={busy || !agree}>
              {busy ? "Confirming…" : "Confirm request"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
