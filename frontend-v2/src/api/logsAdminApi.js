// The admin developer log: find an account, then fetch its log to download.
// Admin-only on the server (`/admin/logs/*`, `require_admin`).
import { request } from './client';

const BASE = '/admin/logs';

export const logsAdminApi = {
  // Accounts whose email or username contains `query` (at most 20).
  searchUsers: (query) => request(`${BASE}/users?q=${encodeURIComponent(query)}`),
  // `{ user, channel, entries }` for one account; every channel when none is given.
  exportLog: (userId, channel) => {
    const params = new URLSearchParams({ user_id: String(userId) });
    if (channel) params.append('channel', channel);
    return request(`${BASE}/export?${params}`);
  },
};

export default logsAdminApi;
