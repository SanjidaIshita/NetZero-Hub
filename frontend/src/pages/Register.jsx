import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { fieldErrors } from "../api.js";
import { useAuth } from "../auth.jsx";
import Field from "../components/Field.jsx";

const FIELDS = [
  ["first_name", "First name", "text", "given-name"],
  ["last_name", "Last name", "text", "family-name"],
  ["email", "Email", "email", "email"],
  ["username", "Username", "text", "username"],
  ["password", "Password", "password", "new-password"],
];

export default function Register() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  // After signing up, open the service the user chose (e.g. /solar), otherwise the dashboard.
  const from = location.state?.from || "/dashboard";
  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", username: "", password: "" });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={from} replace />;

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    setError("");
    try {
      await register(form);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      const fe = fieldErrors(err);
      if (Object.keys(fe).length) setErrors(fe);
      else setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-layout">
      <section className="auth-intro">
        <h1>Create your NetZero Hub account</h1>
        <p>ou need an account to book and manage your services.</p>
      </section>
      <form className="card auth-card" onSubmit={submit}>
        <h2>Register</h2>
        {(error || errors.non_field_errors) && (
          <p className="alert alert-error">{error || errors.non_field_errors}</p>
        )}
        <div className="grid-2">
          {FIELDS.slice(0, 2).map(([name, label, type, ac]) => (
            <Field key={name} label={label} id={name} error={errors[name]}>
              <input
                id={name}
                type={type}
                autoComplete={ac}
                value={form[name]}
                onChange={(e) => setForm({ ...form, [name]: e.target.value })}
              />
            </Field>
          ))}
        </div>
        {FIELDS.slice(2).map(([name, label, type, ac]) => (
          <Field
            key={name}
            label={label}
            id={name}
            error={errors[name]}
            hint={name === "password" ? "At least 8 characters, not entirely numeric." : undefined}
          >
            <input
              id={name}
              type={type}
              autoComplete={ac}
              value={form[name]}
              onChange={(e) => setForm({ ...form, [name]: e.target.value })}
              required
            />
          </Field>
        ))}
        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>
        <p className="muted small">
          Already registered? <Link to="/login" state={{ from: location.state?.from }}>Sign in</Link>
        </p>
      </form>
    </div>
  );
}
