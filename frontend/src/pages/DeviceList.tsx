import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  api,
  type CredentialProfile,
  type Device,
  type Platform,
  type Site,
} from '../api/client';

const PLATFORMS: Platform[] = ['cisco_ios', 'cisco_nxos', 'arista_eos', 'juniper_junos'];

export function DeviceList() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [profiles, setProfiles] = useState<CredentialProfile[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Device | null>(null);

  const load = () => {
    setLoading(true);
    Promise.all([api.listDevices(), api.listCredentialProfiles(), api.listSites()])
      .then(([deviceList, profileList, siteList]) => {
        setDevices(deviceList);
        setProfiles(profileList);
        setSites(siteList);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const startEdit = (device: Device) => {
    setEditingId(device.id);
    setDraft({ ...device });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setDraft(null);
  };

  const saveEdit = () => {
    if (!draft) return;
    setError(null);
    api
      .updateDevice(draft.id, {
        name: draft.name,
        management_address: draft.management_address,
        ssh_port: draft.ssh_port,
        platform: draft.platform,
        site: draft.site,
        credential_profile_id: draft.credential_profile_id,
      })
      .then(() => {
        cancelEdit();
        load();
      })
      .catch((err: Error) => setError(err.message));
  };

  const deleteDevice = (device: Device) => {
    if (!window.confirm(`Delete ${device.name}? This can't be undone.`)) return;
    setError(null);
    api
      .deleteDevice(device.id)
      .then(load)
      .catch((err: Error) => setError(err.message));
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Devices</h1>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p>Loading…</p>}

      {!loading && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Management address</th>
              <th>Platform</th>
              <th>Site</th>
              <th>Credential profile</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {devices.map((device) =>
              editingId === device.id && draft ? (
                <tr key={device.id}>
                  <td>
                    <input
                      value={draft.name}
                      onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={draft.management_address}
                      onChange={(e) =>
                        setDraft({ ...draft, management_address: e.target.value })
                      }
                    />
                    <input
                      type="number"
                      value={draft.ssh_port}
                      onChange={(e) =>
                        setDraft({ ...draft, ssh_port: Number(e.target.value) })
                      }
                    />
                  </td>
                  <td>
                    <select
                      value={draft.platform}
                      onChange={(e) =>
                        setDraft({ ...draft, platform: e.target.value as Platform })
                      }
                    >
                      {PLATFORMS.map((platform) => (
                        <option key={platform} value={platform}>
                          {platform}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      value={draft.site ?? ''}
                      onChange={(e) => setDraft({ ...draft, site: e.target.value || null })}
                    >
                      <option value="">—</option>
                      {sites.map((site) => (
                        <option key={site.id} value={site.name}>
                          {site.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      value={draft.credential_profile_id ?? ''}
                      onChange={(e) =>
                        setDraft({ ...draft, credential_profile_id: e.target.value || null })
                      }
                    >
                      <option value="">—</option>
                      {profiles.map((profile) => (
                        <option key={profile.id} value={profile.id}>
                          {profile.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <button type="button" onClick={saveEdit}>
                      Save
                    </button>
                    <button type="button" onClick={cancelEdit}>
                      Cancel
                    </button>
                  </td>
                </tr>
              ) : (
                <tr key={device.id}>
                  <td>{device.name}</td>
                  <td>
                    {device.management_address}:{device.ssh_port}
                  </td>
                  <td>{device.platform}</td>
                  <td>{device.site ?? '—'}</td>
                  <td>
                    {profiles.find((p) => p.id === device.credential_profile_id)?.name ?? '—'}
                  </td>
                  <td>
                    <span className="row-actions">
                      <Link to={`/devices/${device.id}`}>Results</Link>
                      <button type="button" onClick={() => startEdit(device)}>
                        Edit
                      </button>
                      <button type="button" onClick={() => deleteDevice(device)}>
                        Delete
                      </button>
                    </span>
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
