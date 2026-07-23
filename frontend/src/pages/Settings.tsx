import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { usersApi, type Role, type User } from '../api/client';

const ROLES: Role[] = ['admin', 'user'];

export function Settings() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<{ username: string; role: Role; password: string } | null>(
    null,
  );

  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState<Role>('user');

  const load = () => {
    setLoading(true);
    usersApi
      .list()
      .then(setUsers)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const startEdit = (user: User) => {
    setEditingId(user.id);
    setDraft({ username: user.username, role: user.role, password: '' });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setDraft(null);
  };

  const saveEdit = (userId: string) => {
    if (!draft) return;
    setError(null);
    usersApi
      .update(userId, {
        username: draft.username,
        role: draft.role,
        password: draft.password || null,
      })
      .then(() => {
        cancelEdit();
        load();
      })
      .catch((err: Error) => setError(err.message));
  };

  const deleteUser = (user: User) => {
    if (!window.confirm(`Delete ${user.username}? This can't be undone.`)) return;
    setError(null);
    usersApi
      .remove(user.id)
      .then(load)
      .catch((err: Error) => setError(err.message));
  };

  const createUser = (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    usersApi
      .create({ username: newUsername, password: newPassword, role: newRole })
      .then(() => {
        setNewUsername('');
        setNewPassword('');
        setNewRole('user');
        load();
      })
      .catch((err: Error) => setError(err.message));
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Settings</h1>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p>Loading…</p>}

      {!loading && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Role</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) =>
              editingId === user.id && draft ? (
                <tr key={user.id}>
                  <td>
                    <input
                      value={draft.username}
                      onChange={(e) => setDraft({ ...draft, username: e.target.value })}
                    />
                  </td>
                  <td>
                    <select
                      value={draft.role}
                      onChange={(e) => setDraft({ ...draft, role: e.target.value as Role })}
                    >
                      {ROLES.map((role) => (
                        <option key={role} value={role}>
                          {role}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      type="password"
                      placeholder="New password (optional)"
                      value={draft.password}
                      onChange={(e) => setDraft({ ...draft, password: e.target.value })}
                    />
                    <span className="row-actions">
                      <button type="button" onClick={() => saveEdit(user.id)}>
                        Save
                      </button>
                      <button type="button" onClick={cancelEdit}>
                        Cancel
                      </button>
                    </span>
                  </td>
                </tr>
              ) : (
                <tr key={user.id}>
                  <td>{user.username}</td>
                  <td>{user.role}</td>
                  <td>
                    <span className="row-actions">
                      <button type="button" onClick={() => startEdit(user)}>
                        Edit
                      </button>
                      <button type="button" onClick={() => deleteUser(user)}>
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

      <h2>Add user</h2>
      <form className="inline-form" onSubmit={createUser}>
        <input
          placeholder="Username"
          value={newUsername}
          onChange={(e) => setNewUsername(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
        />
        <select value={newRole} onChange={(e) => setNewRole(e.target.value as Role)}>
          {ROLES.map((role) => (
            <option key={role} value={role}>
              {role}
            </option>
          ))}
        </select>
        <button type="submit">Add user</button>
      </form>
    </div>
  );
}
