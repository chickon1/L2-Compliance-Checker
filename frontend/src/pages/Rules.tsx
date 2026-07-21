import { Fragment, useEffect, useState } from 'react';
import { api, type Platform, type Rule } from '../api/client';

const VENDOR_LABELS: Record<string, string> = {
  '': 'All platforms',
  cisco_ios: 'Cisco (IOS / IOS-XE)',
  cisco_nxos: 'Cisco (NX-OS)',
  'cisco_ios,cisco_nxos': 'Cisco (IOS / IOS-XE / NX-OS)',
  arista_eos: 'Arista EOS',
  juniper_junos: 'Juniper Junos',
};

function vendorGroupFor(platforms: Platform[]): string {
  const key = [...platforms].sort().join(',');
  return VENDOR_LABELS[key] ?? platforms.join(', ');
}

export function Rules() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    api
      .listRules()
      .then(setRules)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

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

  const toggleGroup = (group: string) => {
    setCollapsedGroups((current) => {
      const next = new Set(current);
      if (next.has(group)) {
        next.delete(group);
      } else {
        next.add(group);
      }
      return next;
    });
  };

  const groups = new Map<string, Rule[]>();
  rules.forEach((rule) => {
    const group = vendorGroupFor(rule.platforms);
    groups.set(group, [...(groups.get(group) ?? []), rule]);
  });

  return (
    <div className="page">
      <div className="page-header">
        <h1>Rules</h1>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p>Loading…</p>}

      {!loading &&
        [...groups.entries()].map(([group, groupRules]) => {
          const groupOpen = !collapsedGroups.has(group);
          return (
            <section key={group} className="rule-group">
              <button
                type="button"
                className="rule-group-header"
                onClick={() => toggleGroup(group)}
              >
                <span className="expand-toggle">{groupOpen ? '▾' : '▸'}</span>
                {group}
                <span className="rule-group-count">{groupRules.length}</span>
              </button>
              {groupOpen && (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th></th>
                      <th>Rule</th>
                      <th>Severity</th>
                      <th>Applies when</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupRules.map((rule) => {
                      const isOpen = expanded.has(rule.id);
                      return (
                        <Fragment key={rule.id}>
                          <tr className="expandable-row" onClick={() => toggle(rule.id)}>
                            <td className="expand-toggle">{isOpen ? '▾' : '▸'}</td>
                            <td>{rule.id}</td>
                            <td className={`severity-${rule.severity}`}>{rule.severity}</td>
                            <td>{rule.applies_if_label ?? 'always'}</td>
                          </tr>
                          {isOpen && (
                            <tr className="detail-row">
                              <td></td>
                              <td colSpan={3}>
                                <p className="rule-description">{rule.description}</p>
                                {rule.notes && <p className="rule-note">{rule.notes}</p>}
                                {rule.fix && (
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
            </section>
          );
        })}
    </div>
  );
}
