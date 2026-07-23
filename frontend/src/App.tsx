import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom';
import { ConsolidatedReport } from './pages/ConsolidatedReport';
import { Dashboard } from './pages/Dashboard';
import { DeviceDetail } from './pages/DeviceDetail';
import { DeviceList } from './pages/DeviceList';
import { Import } from './pages/Import';
import { Report } from './pages/Report';
import { Reports } from './pages/Reports';
import { Rules } from './pages/Rules';

function App() {
  return (
    <BrowserRouter>
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
          </nav>
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
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
