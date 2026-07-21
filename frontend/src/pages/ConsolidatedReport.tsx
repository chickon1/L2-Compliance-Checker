import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  api,
  type Device,
  type DeviceCheckResult,
  type Rule,
} from '../api/client';

function countByStatus(results: DeviceCheckResult[], status: string): number {
  return results.reduce(
    (total, r) => total + r.rule_results.filter((rr) => rr.status === status).length,
    0,
  );
}

export function ConsolidatedReport() {
  const [searchParams] = useSearchParams();
  const deviceIds = (searchParams.get('ids') ?? '').split(',').filter(Boolean);

  const [devices, setDevices] = useState<Device[]>([]);
  const [results, setResults] = useState<DeviceCheckResult[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (deviceIds.length === 0) {
      setLoading(false);
      return;
    }
    Promise.all([api.listDevices(), api.latestResults(), api.listRules()])
      .then(([allDevices, run, ruleList]) => {
        const idSet = new Set(deviceIds);
        setDevices(allDevices.filter((d) => idSet.has(d.id)));
        setResults((run?.device_results ?? []).filter((r) => idSet.has(r.device_id)));
        setRules(ruleList);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams.toString()]);

  const rulesById = new Map(rules.map((rule) => [rule.id, rule]));
  const resultsByDevice = new Map(results.map((r) => [r.device_id, r]));

  const sites = [...new Set(devices.map((d) => d.site ?? '(No site)'))];
  const totalPassed = countByStatus(results, 'pass');
  const totalFailed = countByStatus(results, 'fail');
  const totalNotApplicable = countByStatus(results, 'not_applicable');

  return (
    <div className="page report-page">
      <div className="page-header no-print">
        <h1>Consolidated Compliance Report</h1>
        <button type="button" onClick={() => window.print()}>
          Print / Save as PDF
        </button>
      </div>

      {error && <p className="error no-print">{error}</p>}
      {loading && <p className="no-print">Loading…</p>}
      {!loading && deviceIds.length === 0 && (
        <p className="no-print">
          No devices selected. Go to the Reports page and pick at least one device.
        </p>
      )}

      {!loading && devices.length > 0 && (
        <div className="report-content">
          <h2 className="report-title">
            Consolidated Compliance Report — {devices.length} device
            {devices.length === 1 ? '' : 's'}
          </h2>
          <dl className="report-meta">
            <div>
              <dt>Sites</dt>
              <dd>{sites.join(', ')}</dd>
            </div>
            <div>
              <dt>Devices</dt>
              <dd>{devices.map((d) => d.name).join(', ')}</dd>
            </div>
            <div>
              <dt>Generated</dt>
              <dd>{new Date().toLocaleString()}</dd>
            </div>
          </dl>

          <div className="summary-cards">
            <div className="card">
              <span className="card-label">Devices</span>
              <span className="card-value">{devices.length}</span>
            </div>
            <div className="card pass">
              <span className="card-label">Total passed</span>
              <span className="card-value">{totalPassed}</span>
            </div>
            <div className="card fail">
              <span className="card-label">Total failed</span>
              <span className="card-value">{totalFailed}</span>
            </div>
            <div className="card">
              <span className="card-label">Total N/A</span>
              <span className="card-value">{totalNotApplicable}</span>
            </div>
          </div>

          {devices.map((device) => {
            const result = resultsByDevice.get(device.id);
            const passed = result ? result.rule_results.filter((r) => r.status === 'pass').length : 0;
            const failed = result ? result.rule_results.filter((r) => r.status === 'fail').length : 0;
            const notApplicable = result
              ? result.rule_results.filter((r) => r.status === 'not_applicable').length
              : 0;

            return (
              <div className="report-device-section" key={device.id}>
                <h3 className="report-title">{device.name}</h3>
                <dl className="report-meta">
                  <div>
                    <dt>Management address</dt>
                    <dd>
                      {device.management_address}:{device.ssh_port}
                    </dd>
                  </div>
                  <div>
                    <dt>Platform</dt>
                    <dd>{device.platform}</dd>
                  </div>
                  <div>
                    <dt>Site</dt>
                    <dd>{device.site ?? '—'}</dd>
                  </div>
                  <div>
                    <dt>Checked at</dt>
                    <dd>{result ? new Date(result.checked_at).toLocaleString() : '—'}</dd>
                  </div>
                </dl>

                {!result && <p className="error">No compliance run has covered this device yet.</p>}
                {result?.collection_error && (
                  <p className="error">Could not collect config: {result.collection_error}</p>
                )}

                {result && !result.collection_error && (
                  <>
                    <div className="summary-cards">
                      <div className="card pass">
                        <span className="card-label">Passed</span>
                        <span className="card-value">{passed}</span>
                      </div>
                      <div className="card fail">
                        <span className="card-label">Failed</span>
                        <span className="card-value">{failed}</span>
                      </div>
                      <div className="card">
                        <span className="card-label">Not applicable</span>
                        <span className="card-value">{notApplicable}</span>
                      </div>
                    </div>

                    <table className="data-table report-table">
                      <thead>
                        <tr>
                          <th>Rule</th>
                          <th>Severity</th>
                          <th>Status</th>
                          <th>Evidence</th>
                          <th>Comments</th>
                          <th>Fix</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.rule_results.map((ruleResult) => {
                          const rule = rulesById.get(ruleResult.rule_id);
                          return (
                            <tr key={ruleResult.rule_id}>
                              <td>
                                <strong>{ruleResult.rule_id}</strong>
                                {rule?.description && (
                                  <p className="rule-description">{rule.description}</p>
                                )}
                              </td>
                              <td className={rule ? `severity-${rule.severity}` : undefined}>
                                {rule?.severity ?? '—'}
                              </td>
                              <td className={ruleResult.status}>
                                {ruleResult.status.replace('_', ' ')}
                              </td>
                              <td>
                                {ruleResult.evidence.length > 0 ? ruleResult.evidence.join(', ') : '—'}
                              </td>
                              <td>{ruleResult.override_comment ?? '—'}</td>
                              <td>
                                {ruleResult.status === 'fail' && rule?.fix ? (
                                  <pre className="fix-block">{rule.fix}</pre>
                                ) : (
                                  '—'
                                )}
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
          })}
        </div>
      )}
    </div>
  );
}
