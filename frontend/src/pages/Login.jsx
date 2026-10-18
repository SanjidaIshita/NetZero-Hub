import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import Field from "../components/Field.jsx";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  // Go back to the page or service the user was trying to open (e.g. /solar), otherwise the dashboard.
  const from = location.state?.from || "/dashboard";
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={from} replace />;

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(form.username, form.password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-layout">
      <section className="auth-intro">
        <h1>Sign in to NetZero Hub</h1>
        <p>
          One account for all our services: book recycling collections, apply for environment protection
          licences and report incidents, and request solar panel installations.
        </p>
      </section>
      <form className="card auth-card" onSubmit={submit}>
        <h2>Sign in</h2>
        {error && <p className="alert alert-error">{error}</p>}
        <Field label="Username" id="username">
          <input
            id="username"
            autoComplete="username"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            required
          />
        </Field>
        <Field label="Password" id="password">
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required
          />
        </Field>
        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="muted small">
          New to NetZero Hub? <Link to="/register" state={{ from: location.state?.from }}>Create an account</Link>
        </p>
      </form>
    </div>
  );
}
