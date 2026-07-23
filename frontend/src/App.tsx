import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ConsolidatedReport } from './pages/ConsolidatedReport';
import { Dashboard } from './pages/Dashboard';
import { DeviceDetail } from './pages/DeviceDetail';
import { DeviceList } from './pages/DeviceList';
import { Import } from './pages/Import';
import { Login } from './pages/Login';
import { Report } from './pages/Report';
import { Reports } from './pages/Reports';
import { Rules } from './pages/Rules';
import { Settings } from './pages/Settings';

function AuthedApp() {
  const { status, loading, logout } = useAuth();

  if (loading) {
    return null;
  }

  if (!status?.authenticated) {
    return <Login />;
  }

  return (
    <div className="app">
      <header className="app-header no-print">
        <span className="app-title">Compliance Checker</span>
        <nav>
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/devices">Devices</NavLink>
          <NavLink to="/import">Import</NavLink>
          <NavLink to="/rules">Rules</NavLink>
          <NavLink to="/reports">Reports</NavLink>
          {status.user?.role === 'admin' && <NavLink to="/settings">Settings</NavLink>}
        </nav>
        <button type="button" className="logout-button" onClick={() => void logout()}>
          Log out
        </button>
        <span className="app-version">v{__APP_VERSION__}</span>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/devices" element={<DeviceList />} />
          <Route path="/devices/:deviceId" element={<DeviceDetail />} />
          <Route path="/import" element={<Import />} />
          <Route path="/rules" element={<Rules />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/report" element={<ConsolidatedReport />} />
          <Route path="/report/:deviceId" element={<Report />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AuthedApp />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
