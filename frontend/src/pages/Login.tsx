import { useState } from 'react';
import type { FormEvent } from 'react';
import { authApi } from '../api/client';
import { useAuth } from '../contexts/AuthContext';

export function Login() {
  const { status, refresh } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setupRequired = status?.setup_required ?? false;

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const call = setupRequired ? authApi.setup(username, password) : authApi.login(username, password);
    call
      .then(() => refresh())
      .catch((err: Error) => setError(err.message))
      .finally(() => setSubmitting(false));
  };

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>{setupRequired ? 'Create admin account' : 'Sign in'}</h1>
        <p className="auth-subtitle">
          {setupRequired
            ? 'No accounts exist yet — create the first one, which becomes an admin.'
            : 'Compliance Checker'}
        </p>
        <label>
          Username
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoFocus
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={submitting}>
          {setupRequired ? 'Create account' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}
