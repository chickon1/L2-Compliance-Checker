import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type ComplianceRun, type ScheduleSettings } from '../api/client';

export function Dashboard() {
  const [run, setRun] = useState<ComplianceRun | null>(null);
  const [currentDeviceIds, setCurrentDeviceIds] = useState<Set<string> | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [schedule, setSchedule] = useState<ScheduleSettings | null>(null);
  const [scheduleSaving, setScheduleSaving] = useState(false);
  const [scheduleError, setScheduleError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    Promise.all([api.latestResults(), api.listDevices()])
      .then(([latestRun, devices]) => {
        setRun(latestRun);
        setCurrentDeviceIds(new Set(devices.map((d) => d.id)));
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);
  useEffect(() => {
    api.getSchedule().then(setSchedule).catch(() => setSchedule(null));
  }, []);

  const saveSchedule = (next: ScheduleSettings) => {
    setSchedule(next);
    setScheduleSaving(true);
    setScheduleError(null);
    api
      .updateSchedule(next)
      .then(setSchedule)
      .catch((err: Error) => setScheduleError(err.message))
      .finally(() => setScheduleSaving(false));
  };

  const handleRunChecks = () => {
    setRunning(true);
    setError(null);
    api
      .runChecks()
      .then(setRun)
      .catch((err: Error) => setError(err.message))
      .finally(() => setRunning(false));
  };

  const visibleDeviceResults = (run?.device_results ?? []).filter(
    (result) => !currentDeviceIds || currentDeviceIds.has(result.device_id),
  );

  const statusesByRule = new Map<string, Set<string>>();
  visibleDeviceResults.forEach((d) => {
    d.rule_results.forEach((r) => {
      const statuses = statusesByRule.get(r.rule_id) ?? new Set<string>();
      statuses.add(r.status);
      statusesByRule.set(r.rule_id, statuses);
    });
  });
  const rulesWithFailures = [...statusesByRule.values()].filter((s) => s.has('fail')).length;
  const rulesFullyPassing = statusesByRule.size - rulesWithFailures;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Dashboard</h1>
        <button type="button" onClick={handleRunChecks} disabled={running}>
          {running ? 'Running…' : 'Run checks'}
        </button>
      </div>

      {schedule && (
        <div className="inline-form" style={{ marginBottom: 20 }}>
          <label className="hostname-toggle">
            <input
              type="checkbox"
              checked={schedule.enabled}
              disabled={scheduleSaving}
              onChange={(e) => saveSchedule({ ...schedule, enabled: e.target.checked })}
            />
            Run automatically every
          </label>
          <input
            type="number"
            min={1}
            value={schedule.interval_hours}
            disabled={scheduleSaving}
            onChange={(e) =>
              setSchedule({ ...schedule, interval_hours: Number(e.target.value) || 1 })
            }
            onBlur={() => saveSchedule(schedule)}
            style={{ width: 70 }}
          />
          <span>hours</span>
        </div>
      )}
      {scheduleError && <p className="error">{scheduleError}</p>}

      {error && <p className="error">{error}</p>}
      {loading && <p>Loading…</p>}

      {!loading && !run && <p>No compliance runs yet. Click "Run checks" to start one.</p>}
      {!loading && run && visibleDeviceResults.length === 0 && (
        <p>
          The last run only covers devices that have since been removed. Click "Run checks" to
          get results for your current device list.
        </p>
      )}

      {run && visibleDeviceResults.length > 0 && (
        <>
          <div className="summary-cards">
            <div className="card">
              <span className="card-label">Devices checked</span>
              <span className="card-value">{visibleDeviceResults.length}</span>
            </div>
            <div className="card pass">
              <span className="card-label">Rules fully passing</span>
              <span className="card-value">{rulesFullyPassing}</span>
            </div>
            <div className="card fail">
              <span className="card-label">Rules with failures</span>
              <span className="card-value">{rulesWithFailures}</span>
            </div>
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>Device</th>
                <th>Passed</th>
                <th>Failed</th>
                <th>N/A</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {visibleDeviceResults.map((result) => {
                if (result.collection_error) {
                  return (
                    <tr key={result.device_id}>
                      <td>{result.device_name}</td>
                      <td className="error" colSpan={3}>
                        Could not collect config: {result.collection_error}
                      </td>
                      <td>
                        <Link to={`/devices/${result.device_id}`}>View</Link>
                      </td>
                    </tr>
                  );
                }
                const passed = result.rule_results.filter((r) => r.status === 'pass').length;
                const failed = result.rule_results.filter((r) => r.status === 'fail').length;
                const notApplicable = result.rule_results.filter(
                  (r) => r.status === 'not_applicable',
                ).length;
                return (
                  <tr key={result.device_id}>
                    <td>{result.device_name}</td>
                    <td className="pass">{passed}</td>
                    <td className={failed > 0 ? 'fail' : undefined}>{failed}</td>
                    <td className="not_applicable">{notApplicable}</td>
                    <td>
                      <Link to={`/devices/${result.device_id}`}>View</Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
