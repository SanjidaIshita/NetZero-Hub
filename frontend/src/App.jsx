import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import Bookings from "./pages/Bookings.jsx";
import NewBooking from "./pages/NewBooking.jsx";
import BookingDetail from "./pages/BookingDetail.jsx";
import ProviderConsole from "./pages/ProviderConsole.jsx";
import Home from "./pages/Home.jsx";
import Services from "./pages/Services.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import SolarRequests from "./pages/solar/SolarRequests.jsx";
import SolarNew from "./pages/solar/SolarNew.jsx";
import SolarDetail from "./pages/solar/SolarDetail.jsx";
function RequireAuth({ children, staff = false }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p className="muted center">Loading…</p>;
  if (!user) return <Navigate to="/home" replace state={{ from: location.pathname }} />;
  if (staff && !user.is_staff) return <Navigate to="/" replace />;
  return children;
}

function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // Go to a clean sign-in page so the next user isn't sent to the previous user's page.
  async function signOut() {
    await logout();
    navigate("/home", { replace: true });
  }

  return (
    <header className="site-header">
      <div className="container header-inner">
        <NavLink to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="18" height="18">
              <path
                d="M7 19h10M12 3l3.5 6h-7L12 3zM5 11l-2 4h5M19 11l2 4h-5"
                stroke="currentColor"
                strokeWidth="2"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <span>
            NetZero Hub <span className="brand-sub">Recycling collections</span>
          </span>
        </NavLink>
        <nav className="nav">
  <NavLink to="/home" end>Home</NavLink>
  <NavLink to="/services">Services</NavLink>

  {!user && <NavLink to="/login">Login</NavLink>}

  {user && (
    <>
      <NavLink to="/bookings">My bookings</NavLink>
      {/* <NavLink to="/book">Book a collection</NavLink> */}
      {user.is_staff && <NavLink to="/provider">Provider console</NavLink>}
      <button className="link-button" onClick={signOut}>
        Sign out
      </button>
    </>
  )}
</nav>
      </div>
    </header>
  );
}

export default function App() {
  return (
    <>
      <Header />
      <main className="container main">
        <Routes>
            <Route
            path="/home"
            element={
                <Home />
            }
          />
             <Route
            path="/services"
            element={
                <Services />
            }
          />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <Bookings />
              </RequireAuth>
            }
          />
          <Route
            path="/book"
            element={
              <RequireAuth>
                <NewBooking />
              </RequireAuth>
            }
          />
          <Route
            path="/bookings/:reference"
            element={
              <RequireAuth>
                <BookingDetail />
              </RequireAuth>
            }
          />
          <Route
            path="/provider"
            element={
              <RequireAuth staff>
                <ProviderConsole />
              </RequireAuth>
            }
          />
               <Route
            path="/dashboard"
            element={
              <RequireAuth>
                <Dashboard />
              </RequireAuth>
            }
          />
          <Route
            path="/solar"
            element={
              <RequireAuth>
                <SolarRequests />
              </RequireAuth>
            }
          />
          <Route
            path="/solar/new"
            element={
              <RequireAuth>
                <SolarNew />
              </RequireAuth>
            }
          />
          <Route
            path="/solar/:reference"
            element={
              <RequireAuth>
                <SolarDetail />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      {/* <footer className="site-footer container">
        Service WMS-002 · Recycling collection scheduling ·{" "}
        <a href="/api/docs/" target="_blank" rel="noreferrer">
          API docs
        </a>
      </footer> */}
    </>
  );
}
