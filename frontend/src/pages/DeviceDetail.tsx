import { Fragment, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  api,
  type DeviceChanges,
  type DeviceCheckResult,
  type Rule,
  type RuleResult,
  type Severity,
} from '../api/client';

const SEVERITY_ORDER: Severity[] = ['high', 'medium', 'low'];

function statusLabel(status: string | null): string {
  return status === null ? 'n/a before' : status.replace('_', ' ');
}

export function DeviceDetail() {
  const { deviceId } = useParams<{ deviceId: string }>();
  const [result, setResult] = useState<DeviceCheckResult | null>(null);
  const [rules, setRules] = useState<Rule[]>([]);
  const [changes, setChanges] = useState<DeviceChanges | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [changesOpen, setChangesOpen] = useState(false);
  const [overrideError, setOverrideError] = useState<string | null>(null);

  useEffect(() => {
    if (!deviceId) return;
    Promise.all([api.deviceResults(deviceId), api.listRules(), api.deviceChanges(deviceId)])
      .then(([deviceResult, ruleList, deviceChanges]) => {
        setResult(deviceResult);
        setRules(ruleList);
        setChanges(deviceChanges);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [deviceId]);

  const rulesById = new Map(rules.map((rule) => [rule.id, rule]));

  const severityOf = (ruleResult: RuleResult): Severity =>
    rulesById.get(ruleResult.rule_id)?.severity ?? 'low';

  const severityCounts = result
    ? result.rule_results.reduce(
        (counts, rr) => {
          const severity = severityOf(rr);
          counts[severity] = (counts[severity] ?? 0) + 1;
          return counts;
        },
        { high: 0, medium: 0, low: 0 } as Record<Severity, number>,
      )
    : null;

  const sortedRuleResults = result
    ? [...result.rule_results].sort(
        (a, b) => SEVERITY_ORDER.indexOf(severityOf(a)) - SEVERITY_ORDER.indexOf(severityOf(b)),
      )
    : [];

  const toggle = (ruleId: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(ruleId)) {
        next.delete(ruleId);
      } else {
        next.add(ruleId);
      }
      return next;
    });
  };

  const updateLocalResult = (ruleId: string, patch: Partial<RuleResult>) => {
    setResult((current) => {
      if (!current) return current;
      return {
        ...current,
        rule_results: current.rule_results.map((r) =>
          r.rule_id === ruleId ? { ...r, ...patch } : r,
        ),
      };
    });
  };

  const markNotApplicable = (ruleId: string) => {
    if (!deviceId) return;
    const comment = window.prompt('Why does this rule not apply to this device?');
    if (!comment) return;
    setOverrideError(null);
    api
      .createOverride(deviceId, ruleId, comment)
      .then(() => updateLocalResult(ruleId, { status: 'not_applicable', override_comment: comment }))
      .catch((err: Error) => setOverrideError(err.message));
  };

  const clearOverride = (ruleId: string) => {
    if (!deviceId) return;
    setOverrideError(null);
    api
      .clearOverride(deviceId, ruleId)
      .then(() => updateLocalResult(ruleId, { status: 'fail', override_comment: null }))
      .catch((err: Error) => setOverrideError(err.message));
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>{result ? result.device_name : 'Device'}</h1>
      </div>

      {error && <p className="error">{error}</p>}
      {overrideError && <p className="error">{overrideError}</p>}
      {loading && <p>Loading…</p>}

      {result && (
        <>
          <p className="checked-at">
            Checked at {new Date(result.checked_at).toLocaleString()}
          </p>
          {changes && changes.previous_checked_at && (
            <div className="rule-group">
              <button
                type="button"
                className="rule-group-header"
                onClick={() => setChangesOpen((current) => !current)}
              >
                <span>{changesOpen ? '▾' : '▸'} Changes since last run</span>
                <span className="rule-group-count">{changes.changes.length}</span>
              </button>
              {changesOpen && (
                <>
                  {changes.changes.length === 0 ? (
                    <p className="rule-description">
                      No changes since {new Date(changes.previous_checked_at).toLocaleString()}.
                    </p>
                  ) : (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Rule</th>
                          <th>Was</th>
                          <th>Now</th>
                        </tr>
                      </thead>
                      <tbody>
                        {changes.changes.map((change) => (
                          <tr key={change.rule_id}>
                            <td>{change.rule_id}</td>
                            <td className={change.previous_status ?? undefined}>
                              {statusLabel(change.previous_status)}
                            </td>
                            <td className={change.current_status ?? undefined}>
                              {statusLabel(change.current_status)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </>
              )}
            </div>
          )}
          {result.collection_error && (
            <p className="error">Could not collect config: {result.collection_error}</p>
          )}
          {!result.collection_error && severityCounts && (
            <div className="summary-cards">
              {SEVERITY_ORDER.map((severity) => (
                <div className="card" key={severity}>
                  <span className="card-label">{severity}</span>
                  <span className={`card-value severity-${severity}`}>
                    {severityCounts[severity]}
                  </span>
                </div>
              ))}
            </div>
          )}
          {!result.collection_error && (
          <table className="data-table">
            <thead>
              <tr>
                <th></th>
                <th>Rule</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Evidence</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sortedRuleResults.map((ruleResult) => {
                const rule = rulesById.get(ruleResult.rule_id);
                const isOpen = expanded.has(ruleResult.rule_id);
                return (
                  <Fragment key={ruleResult.rule_id}>
                    <tr className="expandable-row" onClick={() => toggle(ruleResult.rule_id)}>
                      <td className="expand-toggle">{isOpen ? '▾' : '▸'}</td>
                      <td>{ruleResult.rule_id}</td>
                      <td className={`severity-${severityOf(ruleResult)}`}>
                        {severityOf(ruleResult)}
                      </td>
                      <td className={ruleResult.status}>
                        {ruleResult.status.replace('_', ' ')}
                      </td>
                      <td>
                        {ruleResult.evidence.length > 0 ? (
                          <code>{ruleResult.evidence.join(', ')}</code>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <span className="row-actions">
                          {ruleResult.status === 'fail' && (
                            <button
                              type="button"
                              onClick={() => markNotApplicable(ruleResult.rule_id)}
                            >
                              Mark N/A
                            </button>
                          )}
                          {ruleResult.status === 'not_applicable' && (
                            <button type="button" onClick={() => clearOverride(ruleResult.rule_id)}>
                              Clear
                            </button>
                          )}
                        </span>
                      </td>
                    </tr>
                    {isOpen && (
                      <tr className="detail-row">
                        <td></td>
                        <td colSpan={5}>
                          {ruleResult.status === 'not_applicable' && ruleResult.override_comment && (
                            <p className="rule-note">
                              Marked not applicable: {ruleResult.override_comment}
                            </p>
                          )}
                          {rule?.notes && <p className="rule-note">{rule.notes}</p>}
                          {rule?.description && (
                            <p className="rule-description">{rule.description}</p>
                          )}
                          {ruleResult.status === 'fail' && rule?.fix && (
                            <>
                              <span className="fix-label">Fix</span>
                              <pre className="fix-block">{rule.fix}</pre>
                            </>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
          )}
        </>
      )}
    </div>
  );
}
