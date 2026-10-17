import { Link } from 'react-router-dom';
import { useAuth } from '../auth.jsx';

const Icon = ({ children }) => (
  <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor"
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
  licence: (
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
  account: (
    <Icon>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </Icon>
  ),
};

const services = [
  {
    icon: 'recycling',
    title: 'Recycling Collection',
    audience: 'Households',
    text: 'Book a free household recycling collection online and track your booking.',
    points: ['Choose a date and materials', 'Confirmed with your collection provider', 'Manage or cancel bookings'],
  },
  {
    icon: 'licence',
    title: 'Environment Protection',
    audience: 'Businesses, operators and the public',
    text: 'Apply for and manage an environment protection licence, and report pollution incidents for investigation.',
    points: ['Apply for and manage a licence', 'Report a pollution incident', 'Follow investigation updates'],
  },
  {
    icon: 'solar',
    title: 'Solar Panel Installation',
    audience: 'Property owners',
    text: 'Request a solar installation for your property, from assessment to completion.',
    points: ['Request a site assessment', 'Compare and accept a quote', 'Schedule your installation'],
    to: '/solar',
    action: 'Open solar installations',
  },
];

export default function Services() {
  const { user } = useAuth();
  return (
    <main className="home">
      <section className="hero hero--compact">
        <div className="hero__inner">
          <h1>What NetZero Hub offers</h1>
          <p>Environmental services designed for citizens, businesses and property owners.</p>
        </div>
      </section>

      <div className="wrap">
        <section className="block block--first">
          <div className="service-grid">
            {services.map((s) => (
              <div key={s.title} className="service">
                <span className="icon-tile">{icons[s.icon]}</span>
                <h3>{s.title}</h3>
                <p className="service__for">For: {s.audience}</p>
                <p>{s.text}</p>
                <ul>
                  {s.points.map((p) => <li key={p}>{p}</li>)}
                </ul>
                {s.to && (
                  <Link
                    to={user ? s.to : '/login'}
                    className="btn btn--primary"
                    style={{ marginTop: 'auto' }}
                  >
                    {user ? s.action : 'Sign in to get started'}
                  </Link>
                )}
              </div>
            ))}
          </div>
          <p className="note">
            If pollution poses immediate danger to life or safety, call emergency services on 000.
          </p>
        </section>

        <section className="member">
          <span className="icon-tile icon-tile--solid">{icons.account}</span>
          <div>
            <h2>Want to use our services?</h2>
            <p>
              To book a collection, apply for a licence, report an incident or request a solar
              installation, you need to be a member of the NetZero Hub portal.
            </p>
          </div>
          <Link to="/login" className="btn btn--primary">Sign in</Link>
        </section>

        {/* <footer className="home-footer">
          <p>NetZero Hub</p>
          <nav aria-label="Footer">
            <Link to="/faq">FAQ</Link>
            <Link to="/contact">Contact</Link>
            <Link to="/privacy">Privacy</Link>
          </nav>
        </footer> */}
      </div>
    </main>
  );
}
