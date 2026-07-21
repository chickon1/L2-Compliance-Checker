import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, type Device, type DeviceCheckResult, type Rule } from '../api/client';

export function Report() {
  const { deviceId } = useParams<{ deviceId: string }>();
  const [device, setDevice] = useState<Device | null>(null);
  const [result, setResult] = useState<DeviceCheckResult | null>(null);
  const [rules, setRules] = useState<Rule[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!deviceId) return;
    Promise.all([api.listDevices(), api.deviceResults(deviceId), api.listRules()])
      .then(([devices, deviceResult, ruleList]) => {
        setDevice(devices.find((d) => d.id === deviceId) ?? null);
        setResult(deviceResult);
        setRules(ruleList);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [deviceId]);

  const rulesById = new Map(rules.map((rule) => [rule.id, rule]));

  const passed = result?.rule_results.filter((r) => r.status === 'pass').length ?? 0;
  const failed = result?.rule_results.filter((r) => r.status === 'fail').length ?? 0;
  const notApplicable =
    result?.rule_results.filter((r) => r.status === 'not_applicable').length ?? 0;

  return (
    <div className="page report-page">
      <div className="page-header no-print">
        <h1>Compliance Report</h1>
        <button type="button" onClick={() => window.print()}>
          Print / Save as PDF
        </button>
      </div>

      {error && <p className="error no-print">{error}</p>}
      {loading && <p className="no-print">Loading…</p>}

      {device && result && (
        <div className="report-content">
          <h2 className="report-title">Compliance Report — {device.name}</h2>
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
              <dd>{new Date(result.checked_at).toLocaleString()}</dd>
            </div>
          </dl>

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
                    <td className={ruleResult.status}>{ruleResult.status.replace('_', ' ')}</td>
                    <td>{ruleResult.evidence.length > 0 ? ruleResult.evidence.join(', ') : '—'}</td>
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
        </div>
      )}
    </div>
  );
}
