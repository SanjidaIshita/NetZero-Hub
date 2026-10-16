import { Link } from 'react-router-dom';

const Icon = ({ children }) => (
  <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor"
       strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {children}
  </svg>
);

const icons = {
  account: (
    <Icon>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </Icon>
  ),
  clock: (
    <Icon>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </Icon>
  ),
  track: (
    <Icon>
      <path d="M4 6h16M4 12h10M4 18h7" />
      <path d="M17 17l2 2 3-4" />
    </Icon>
  ),
};

const steps = [
  { title: 'Become a member', text: 'Create an account from the sign-in page.' },
  { title: 'Choose a service', text: 'Recycling, licences, pollution reports or solar.' },
  { title: 'Submit your details', text: 'Complete a short form. We tell you if anything is missing.' },
  { title: 'Track progress', text: 'See status updates and decisions in your account.' },
];

const benefits = [
  { icon: 'account', title: 'One account', text: 'Use a single sign-in for all three services.' },
  { icon: 'clock', title: 'Online anytime', text: 'Apply, book and report from any device, day or night.' },
  { icon: 'track', title: 'Track progress', text: 'See the status of every request in one place.' },
];

// Edit these to match how your portal really works.
const faqs = [
  {
    q: 'Do I need an account to use the services?',
    a: 'Yes. To book, apply, report or request an installation you need to be a member of the portal. Anyone can read the Resources and Services pages.',
  },
  {
    q: 'How do I become a member?',
    a: 'Go to the sign-in page and choose "Create an account".',
  },
  {
    q: 'Is recycling collection free?',
    a: 'Standard recycling collections are free.',
  },
  {
    q: 'What if pollution is causing immediate danger?',
    a: 'Call emergency services on 000 first. Then report the incident through the portal so it can be investigated.',
  },
  {
    q: 'How do I check on a request I have made?',
    a: 'Sign in and open your account. Each request shows its current status.',
  },
];

// These describe the service itself. Swap in live numbers from your backend later if you like.
const stats = [
  { value: '3', label: 'Services in one account' },
  { value: '24/7', label: 'Online access' },
  { value: 'Free', label: 'Standard recycling collections' },
];

// Optional: put a photo at public/hero.jpg to show it faintly behind the green.
const heroStyle = {
  backgroundImage:
    'linear-gradient(135deg, rgba(9, 52, 34, 0.94), rgba(23, 112, 74, 0.86)), url(/hero.jpg)',
};

export default function Home() {
  return (
    <main className="home">
      <section className="hero" style={heroStyle}>
        <div className="hero__inner">
          <h1>Welcome to NetZero Hub</h1>
          <p>
            Recycling, licences, pollution reporting and solar installation. Simple, fast and
            available online whenever you need it.
          </p>
        </div>
      </section>

      <div className="wrap">
        <div className="stats">
          {stats.map((s) => (
            <div key={s.label} className="stat">
              <strong>{s.value}</strong>
              <span>{s.label}</span>
            </div>
          ))}
        </div>

        <section className="block">
          <h2 className="block__title">How it works</h2>
          <ol className="steps">
            {steps.map((s) => (
              <li key={s.title}>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="block">
          <h2 className="block__title">Why Choose NetZero Hub?</h2>
          <div className="benefit-grid">
            {benefits.map((b) => (
              <div key={b.title} className="benefit">
                <span className="icon-tile">{icons[b.icon]}</span>
                <h3>{b.title}</h3>
                <p>{b.text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="block">
          <h2 className="block__title">Frequently asked questions</h2>
          <div className="faq">
            {faqs.map((f) => (
              <details key={f.q}>
                <summary>{f.q}</summary>
                <p>{f.a}</p>
              </details>
            ))}
          </div>
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
