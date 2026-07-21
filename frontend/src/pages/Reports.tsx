import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, type Device } from '../api/client';

const NO_SITE = '(No site)';

export function Reports() {
  const navigate = useNavigate();
  const [devices, setDevices] = useState<Device[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listDevices()
      .then(setDevices)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const bySite = new Map<string, Device[]>();
  devices.forEach((device) => {
    const key = device.site ?? NO_SITE;
    bySite.set(key, [...(bySite.get(key) ?? []), device]);
  });

  const toggleDevice = (deviceId: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(deviceId)) {
        next.delete(deviceId);
      } else {
        next.add(deviceId);
      }
      return next;
    });
  };

  const toggleSite = (siteDevices: Device[]) => {
    const allSelected = siteDevices.every((d) => selected.has(d.id));
    setSelected((current) => {
      const next = new Set(current);
      siteDevices.forEach((d) => (allSelected ? next.delete(d.id) : next.add(d.id)));
      return next;
    });
  };

  const generateReport = () => {
    if (selected.size === 0) return;
    navigate(`/report?ids=${[...selected].join(',')}`);
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Reports</h1>
        <button type="button" onClick={generateReport} disabled={selected.size === 0}>
          Generate report for {selected.size} selected
        </button>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p>Loading…</p>}

      {!loading &&
        [...bySite.entries()].map(([site, siteDevices]) => (
          <section className="rule-group" key={site}>
            <div className="rule-group-header">
              <label className="hostname-toggle">
                <input
                  type="checkbox"
                  checked={siteDevices.every((d) => selected.has(d.id))}
                  onChange={() => toggleSite(siteDevices)}
                />
                <strong>{site}</strong>
              </label>
              <span className="rule-group-count">{siteDevices.length}</span>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th></th>
                  <th>Device</th>
                  <th>Management address</th>
                  <th>Platform</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {siteDevices.map((device) => (
                  <tr key={device.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selected.has(device.id)}
                        onChange={() => toggleDevice(device.id)}
                      />
                    </td>
                    <td>{device.name}</td>
                    <td>{device.management_address}</td>
                    <td>{device.platform}</td>
                    <td>
                      <Link to={`/report/${device.id}`}>View alone</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ))}
    </div>
  );
}
