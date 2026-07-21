import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  api,
  type CredentialProfile,
  type DiscoveredHost,
  type Platform,
  type Site,
} from '../api/client';

const PLATFORMS: Platform[] = ['cisco_ios', 'cisco_nxos', 'arista_eos', 'juniper_junos'];
const NEW_SITE = '__new__';

interface ScanRow {
  host: DiscoveredHost;
  included: boolean;
  useDetectedHostname: boolean;
  name: string;
  platform: Platform | '';
  site: string;
}

function toRow(host: DiscoveredHost): ScanRow {
  return {
    host,
    included: host.auth_ok,
    useDetectedHostname: Boolean(host.guessed_hostname),
    name: host.guessed_hostname ?? host.address,
    platform: host.guessed_platform ?? '',
    site: '',
  };
}

export function Import() {
  const navigate = useNavigate();

  const [profiles, setProfiles] = useState<CredentialProfile[]>([]);
  const [sites, setSites] = useState<Site[]>([]);

  const [profileName, setProfileName] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [profileError, setProfileError] = useState<string | null>(null);

  const [range, setRange] = useState('192.168.100.0/24');
  const [selectedProfileId, setSelectedProfileId] = useState('');
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [rows, setRows] = useState<ScanRow[]>([]);

  const [bulkSite, setBulkSite] = useState('');
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);

  const loadProfiles = () => api.listCredentialProfiles().then(setProfiles);
  const loadSites = () => api.listSites().then(setSites);

  useEffect(() => {
    loadProfiles();
    loadSites();
  }, []);

  const handleCreateProfile = (event: React.FormEvent) => {
    event.preventDefault();
    setProfileError(null);
    api
      .createCredentialProfile({ name: profileName, username, password })
      .then((profile) => {
        setProfileName('');
        setUsername('');
        setPassword('');
        setSelectedProfileId(profile.id);
        return loadProfiles();
      })
      .catch((err: Error) => setProfileError(err.message));
  };

  const editProfile = (profile: CredentialProfile) => {
    const newName = window.prompt('Profile name', profile.name);
    if (!newName) return;
    const newUsername = window.prompt('Username', profile.username);
    if (!newUsername) return;
    const newPassword = window.prompt('New password (leave blank to keep the current one)');
    setProfileError(null);
    api
      .updateCredentialProfile(profile.id, {
        name: newName,
        username: newUsername,
        password: newPassword || null,
      })
      .then(loadProfiles)
      .catch((err: Error) => setProfileError(err.message));
  };

  const deleteProfile = (profile: CredentialProfile) => {
    if (
      !window.confirm(
        `Delete credential profile "${profile.name}"? Devices using it will fail to collect until reassigned.`,
      )
    ) {
      return;
    }
    setProfileError(null);
    api
      .deleteCredentialProfile(profile.id)
      .then(loadProfiles)
      .catch((err: Error) => setProfileError(err.message));
  };

  const handleScan = (event: React.FormEvent) => {
    event.preventDefault();
    setScanError(null);
    setScanning(true);
    api
      .scan(range, selectedProfileId)
      .then((hosts) => setRows(hosts.map(toRow)))
      .catch((err: Error) => setScanError(err.message))
      .finally(() => setScanning(false));
  };

  const updateRow = (address: string, patch: Partial<ScanRow>) => {
    setRows((current) =>
      current.map((row) => (row.host.address === address ? { ...row, ...patch } : row)),
    );
  };

  const handleCreateSiteForRow = async (address: string, name: string) => {
    const site = await api.createSite(name);
    setSites((current) => [...current, site]);
    updateRow(address, { site: site.name });
  };

  const applyBulkSite = () => {
    if (!bulkSite) return;
    setRows((current) => current.map((row) => ({ ...row, site: bulkSite })));
  };

  const handleImport = () => {
    setImportError(null);
    const selected = rows.filter((row) => row.included && row.platform);
    if (selected.length === 0) {
      setImportError('Select at least one host with a platform set.');
      return;
    }
    setImporting(true);
    api
      .importDevices(
        selected.map((row) => ({
          name: row.name,
          management_address: row.host.address,
          ssh_port: 22,
          platform: row.platform as Platform,
          site: row.site || null,
          credential_profile_id: selectedProfileId || null,
        })),
      )
      .then(() => navigate('/devices'))
      .catch((err: Error) => setImportError(err.message))
      .finally(() => setImporting(false));
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Import devices</h1>
      </div>

      <section className="import-section">
        <h2>Credential profiles</h2>
        {profiles.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Username</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((profile) => (
                <tr key={profile.id}>
                  <td>{profile.name}</td>
                  <td>{profile.username}</td>
                  <td>
                    <span className="row-actions">
                      <button type="button" onClick={() => editProfile(profile)}>
                        Edit
                      </button>
                      <button type="button" onClick={() => deleteProfile(profile)}>
                        Delete
                      </button>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <form className="inline-form" onSubmit={handleCreateProfile}>
          <input
            placeholder="Profile name"
            value={profileName}
            onChange={(e) => setProfileName(e.target.value)}
            required
          />
          <input
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button type="submit">Add profile</button>
        </form>
        {profileError && <p className="error">{profileError}</p>}
      </section>

      <section className="import-section">
        <h2>Scan for devices</h2>
        <form className="inline-form" onSubmit={handleScan}>
          <input
            placeholder="192.168.100.0/24 or 192.168.100.1-20"
            value={range}
            onChange={(e) => setRange(e.target.value)}
            required
          />
          <select
            value={selectedProfileId}
            onChange={(e) => setSelectedProfileId(e.target.value)}
            required
          >
            <option value="" disabled>
              Credential profile
            </option>
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name}
              </option>
            ))}
          </select>
          <button type="submit" disabled={scanning || !selectedProfileId}>
            {scanning ? 'Scanning…' : 'Scan'}
          </button>
        </form>
        {scanError && <p className="error">{scanError}</p>}
      </section>

      {rows.length > 0 && (
        <section className="import-section">
          <h2>Results</h2>
          <div className="bulk-site">
            <select value={bulkSite} onChange={(e) => setBulkSite(e.target.value)}>
              <option value="">Set site for all…</option>
              {sites.map((site) => (
                <option key={site.id} value={site.name}>
                  {site.name}
                </option>
              ))}
            </select>
            <button type="button" onClick={applyBulkSite}>
              Apply to all
            </button>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th></th>
                <th>Address</th>
                <th>Status</th>
                <th>Name</th>
                <th>Platform</th>
                <th>Site</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.host.address}>
                  <td>
                    <input
                      type="checkbox"
                      checked={row.included}
                      onChange={(e) =>
                        updateRow(row.host.address, { included: e.target.checked })
                      }
                    />
                  </td>
                  <td>{row.host.address}</td>
                  <td className={row.host.auth_ok ? 'pass' : 'fail'}>
                    {!row.host.reachable
                      ? 'unreachable'
                      : row.host.auth_ok
                        ? 'authenticated'
                        : 'auth failed'}
                  </td>
                  <td>
                    <label className="hostname-toggle">
                      <input
                        type="checkbox"
                        checked={row.useDetectedHostname}
                        disabled={!row.host.guessed_hostname}
                        onChange={(e) =>
                          updateRow(row.host.address, {
                            useDetectedHostname: e.target.checked,
                            name: e.target.checked
                              ? (row.host.guessed_hostname ?? row.name)
                              : row.name,
                          })
                        }
                      />
                      use detected
                    </label>
                    <input
                      value={row.name}
                      disabled={row.useDetectedHostname}
                      onChange={(e) => updateRow(row.host.address, { name: e.target.value })}
                    />
                  </td>
                  <td>
                    <select
                      value={row.platform}
                      onChange={(e) =>
                        updateRow(row.host.address, { platform: e.target.value as Platform })
                      }
                    >
                      <option value="">—</option>
                      {PLATFORMS.map((platform) => (
                        <option key={platform} value={platform}>
                          {platform}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      value={sites.some((s) => s.name === row.site) ? row.site : ''}
                      onChange={(e) => {
                        if (e.target.value === NEW_SITE) {
                          const name = window.prompt('New site name');
                          if (name) void handleCreateSiteForRow(row.host.address, name);
                          return;
                        }
                        updateRow(row.host.address, { site: e.target.value });
                      }}
                    >
                      <option value="">—</option>
                      {sites.map((site) => (
                        <option key={site.id} value={site.name}>
                          {site.name}
                        </option>
                      ))}
                      <option value={NEW_SITE}>+ Add new site…</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {importError && <p className="error">{importError}</p>}
          <button type="button" onClick={handleImport} disabled={importing}>
            {importing ? 'Adding…' : 'Add selected devices'}
          </button>
        </section>
      )}
    </div>
  );
}
