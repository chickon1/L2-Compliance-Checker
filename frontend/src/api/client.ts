export type Platform = 'cisco_ios' | 'cisco_nxos' | 'arista_eos' | 'juniper_junos';

export interface Device {
  id: string;
  name: string;
  management_address: string;
  ssh_port: number;
  platform: Platform;
  site: string | null;
  credential_profile_id: string | null;
}

export interface DeviceCreate {
  name: string;
  management_address: string;
  ssh_port: number;
  platform: Platform;
  site: string | null;
  credential_profile_id: string | null;
}

export type Severity = 'low' | 'medium' | 'high';

export interface Rule {
  id: string;
  description: string;
  severity: Severity;
  require: string[];
  forbid: string[];
  platforms: Platform[];
  applies_if: string[];
  applies_if_label: string | null;
  notes: string | null;
  fix: string | null;
}

export type RuleStatus = 'pass' | 'fail' | 'not_applicable';

export interface RuleResult {
  rule_id: string;
  status: RuleStatus;
  evidence: string[];
  override_comment: string | null;
}

export interface ResultOverride {
  device_id: string;
  rule_id: string;
  comment: string;
  created_at: string;
}

export interface DeviceCheckResult {
  device_id: string;
  device_name: string;
  checked_at: string;
  rule_results: RuleResult[];
  collection_error: string | null;
}

export interface ComplianceRun {
  id: string;
  started_at: string;
  finished_at: string | null;
  device_results: DeviceCheckResult[];
}

export interface CredentialProfile {
  id: string;
  name: string;
  username: string;
}

export interface CredentialProfileCreate {
  name: string;
  username: string;
  password: string;
}

export interface CredentialProfileUpdate {
  name: string;
  username: string;
  password: string | null;
}

export interface Site {
  id: string;
  name: string;
}

export interface DiscoveredHost {
  address: string;
  reachable: boolean;
  auth_ok: boolean;
  guessed_platform: Platform | null;
  guessed_hostname: string | null;
}

export interface RuleChange {
  rule_id: string;
  previous_status: RuleStatus | null;
  current_status: RuleStatus | null;
}

export interface DeviceChanges {
  device_id: string;
  previous_checked_at: string | null;
  current_checked_at: string;
  changes: RuleChange[];
}

export interface ScheduleSettings {
  enabled: boolean;
  interval_hours: number;
}

export type Role = 'admin' | 'user';

export interface User {
  id: string;
  username: string;
  role: Role;
}

export interface UserCreate {
  username: string;
  password: string;
  role: Role;
}

export interface UserUpdate {
  username: string;
  role: Role;
  password: string | null;
}

export interface AuthStatus {
  setup_required: boolean;
  authenticated: boolean;
  user: User | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    ...init,
  });
  if (!response.ok) {
    throw new Error(`${init?.method ?? 'GET'} ${path} failed: ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  listDevices: () => request<Device[]>('/devices'),
  importDevices: (devices: DeviceCreate[]) =>
    request<Device[]>('/devices/import', {
      method: 'POST',
      body: JSON.stringify({ devices }),
    }),
  updateDevice: (deviceId: string, device: DeviceCreate) =>
    request<Device>(`/devices/${deviceId}`, {
      method: 'PATCH',
      body: JSON.stringify(device),
    }),
  deleteDevice: (deviceId: string) =>
    request<void>(`/devices/${deviceId}`, { method: 'DELETE' }),
  listRules: () => request<Rule[]>('/rules'),
  runChecks: (deviceIds?: string[]) =>
    request<ComplianceRun>('/checks/run', {
      method: 'POST',
      body: JSON.stringify({ device_ids: deviceIds ?? null }),
    }),
  latestResults: () => request<ComplianceRun | null>('/checks/results'),
  deviceResults: (deviceId: string) =>
    request<DeviceCheckResult>(`/checks/results/${deviceId}`),
  deviceChanges: (deviceId: string) =>
    request<DeviceChanges | null>(`/checks/results/${deviceId}/changes`),
  getSchedule: () => request<ScheduleSettings>('/schedule'),
  updateSchedule: (settings: ScheduleSettings) =>
    request<ScheduleSettings>('/schedule', {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),
  listCredentialProfiles: () => request<CredentialProfile[]>('/credential-profiles'),
  createCredentialProfile: (profile: CredentialProfileCreate) =>
    request<CredentialProfile>('/credential-profiles', {
      method: 'POST',
      body: JSON.stringify(profile),
    }),
  updateCredentialProfile: (profileId: string, update: CredentialProfileUpdate) =>
    request<CredentialProfile>(`/credential-profiles/${profileId}`, {
      method: 'PATCH',
      body: JSON.stringify(update),
    }),
  deleteCredentialProfile: (profileId: string) =>
    request<void>(`/credential-profiles/${profileId}`, { method: 'DELETE' }),
  listSites: () => request<Site[]>('/sites'),
  createSite: (name: string) =>
    request<Site>('/sites', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  scan: (range: string, credentialProfileId: string, port = 22) =>
    request<DiscoveredHost[]>('/discovery/scan', {
      method: 'POST',
      body: JSON.stringify({ range, credential_profile_id: credentialProfileId, port }),
    }),
  createOverride: (deviceId: string, ruleId: string, comment: string) =>
    request<ResultOverride>(`/devices/${deviceId}/results/${ruleId}/override`, {
      method: 'POST',
      body: JSON.stringify({ comment }),
    }),
  clearOverride: (deviceId: string, ruleId: string) =>
    request<void>(`/devices/${deviceId}/results/${ruleId}/override`, {
      method: 'DELETE',
    }),
};

export const authApi = {
  status: () => request<AuthStatus>('/auth/status'),
  setup: (username: string, password: string) =>
    request<User>('/auth/setup', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  login: (username: string, password: string) =>
    request<User>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
};

export const usersApi = {
  list: () => request<User[]>('/users'),
  create: (user: UserCreate) =>
    request<User>('/users', {
      method: 'POST',
      body: JSON.stringify(user),
    }),
  update: (userId: string, update: UserUpdate) =>
    request<User>(`/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(update),
    }),
  remove: (userId: string) => request<void>(`/users/${userId}`, { method: 'DELETE' }),
};
