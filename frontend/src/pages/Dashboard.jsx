import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

const Icon = ({ children }) => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
       strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {children}
  </svg>
);

const icons = {
  recycling: (
    <Icon>
      <path d="M21 12a9 9 0 0 1-15.5 6.2M3 12A9 9 0 0 1 18.5 5.8" />
      <path d="M18.5 2v4h-4M5.5 22v-4h4" />
    </Icon>
  ),
  environment: (
    <Icon>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5M9 14l2 2 4-4" />
    </Icon>
  ),
  solar: (
    <Icon>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </Icon>
  ),
};

// Change these to your real routes.
const cards = [
  {
    key: 'recycling',
    color: 'green',
    title: 'Recycling Collections',
    text: 'View your collection bookings, confirmed dates, and booking references.',
    viewLabel: 'View Collections',
    viewTo: '/bookings',
    newLabel: 'New Collection',
    newTo: '/book',
  },
  {
    key: 'environment',
    color: 'blue',
    title: 'Environment Protection',
    text: 'Track your licence applications and pollution reports, with status updates and reference numbers.',
    viewLabel: 'View Requests',
    viewTo: '/environment',
    newLabel: 'New Request',
    newTo: '/environment/new',
  },
  {
    key: 'solar',
    color: 'amber',
    title: 'Solar Installations',
    text: 'Follow your solar installation request from site assessment through to completion.',
    viewLabel: 'View Installations',
    viewTo: '/solar',
    newLabel: 'New Request',
    newTo: '/solar/new',
  },
];

/*
  Expected response from GET /api/dashboard (all fields optional):
  { "recycling_count": 3, "environment_count": 1, "solar_count": 0 }
*/
export default function Dashboard() {
  const [counts, setCounts] = useState(null);

  useEffect(() => {
    // Adjust this URL to match your Python backend route.
    fetch('/api/dashboard', { credentials: 'include' })
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) =>
        setCounts({
          recycling: data.recycling_count ?? 0,
          environment: data.environment_count ?? 0,
          solar: data.solar_count ?? 0,
        })
      )
      .catch(() => setCounts(null));
  }, []);

  return (
    <main className="dash">
      <section className="dash-main">
        <h1>My Services Dashboard</h1>
        <p className="dash-sub">
          Quickly access your collections, licence applications, pollution reports, and solar
          installation requests in one place.
        </p>

        <div className="dash-grid">
          {cards.map((c) => (
            <article key={c.key} className="dash-card">
              <div className="dash-card__top">
                <span className={`dash-icon dash-icon--${c.color}`}>{icons[c.key]}</span>
              </div>
              <div className="dash-card__title">
                <h2>{c.title}</h2>
                <span className="dash-count" aria-label={`${counts ? counts[c.key] : 'Unknown number of'} records`}>
                  {counts ? counts[c.key] : '–'}
                </span>
              </div>
              <p>{c.text}</p>
              <div className="dash-actions">
                <Link to={c.viewTo} className="btn btn--primary">{c.viewLabel}</Link>
                <Link to={c.newTo} className="btn btn--secondary">{c.newLabel}</Link>
              </div>
            </article>
          ))}
        </div>

        <p className="dash-note">
          If pollution poses immediate danger to life or safety, call emergency services on 000.
        </p>
      </section>

      <footer className="dash-footer">
        <p>&copy; 2026 NetZero Hub. All rights reserved.</p>
      </footer>
    </main>
  );
}
