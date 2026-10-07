import React from 'react'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Input } from '../components/Input'
import CatalogNoticeBar from '../components/catalog/CatalogNoticeBar'
import { mutedTextStyle } from '../components/catalog/textStyles'
import { logsAdminApi } from '../api/logsAdminApi'
import { useAdminAction } from '../hooks/useAdminAction'
import { downloadJson } from '../utils/download'

// The areas that write to the developer log. `''` downloads every channel.
const CHANNELS = [
  { value: '', label: 'All channels' },
  { value: 'planner', label: 'Planner' },
]

const headingStyle = { margin: 0, fontSize: 'var(--text-lg)', color: 'var(--text-strong)' }

/**
 * The developer log, read the only way it is meant to be read: find an account,
 * then download its log as JSON to inspect offline. The page shows no log
 * content itself -- a planner trace is hundreds of lines of score breakdowns,
 * which a file and an editor handle far better than a screen.
 */
export default function LogsAdminPage() {
  const [query, setQuery] = React.useState('')
  // The query the results belong to, and the results; null before any search.
  const [results, setResults] = React.useState(null)
  const [searched, setSearched] = React.useState('')
  const [selected, setSelected] = React.useState(null)
  const [channel, setChannel] = React.useState('')
  // { kind: 'status' | 'alert', text } -- the kind doubles as the ARIA role.
  const [notice, setNotice] = React.useState(null)
  const { busy, run } = useAdminAction(setNotice)

  const search = (event) => {
    event.preventDefault()
    const text = query.trim()
    if (!text) return undefined
    return run('search the accounts', async () => {
      setResults(await logsAdminApi.searchUsers(text))
      setSearched(text)
      setSelected(null)
    })
  }

  const download = () =>
    run('download the log', async () => {
      const log = await logsAdminApi.exportLog(selected.id, channel || undefined)
      const name = selected.username || `user-${selected.id}`
      downloadJson(log, `devlog-${name}${channel ? `-${channel}` : ''}.json`)
      return `Downloaded ${log.entries.length} entries for ${selected.email}.`
    })

  return (
    <div className="flex flex-col gap-4">
      <div className="min-w-0">
        <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', color: 'var(--text-strong)' }}>
          Developer logs
        </h1>
        <p style={{ ...mutedTextStyle, marginTop: 4 }}>
          Find an account, then download what the app recorded for it, such as why the planner
          picked each dish. Entries are kept for 90 days.
        </p>
      </div>

      <Card>
        <form className="flex flex-wrap items-end gap-3" onSubmit={search}>
          <label className="flex min-w-0 flex-1 flex-col gap-2" style={mutedTextStyle}>
            Email or username
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="cook@example.com"
              autoComplete="off"
            />
          </label>
          <Button type="submit" variant="primary" disabled={busy || !query.trim()}>
            Search
          </Button>
        </form>
      </Card>

      {results !== null && (
        <AccountList
          results={results}
          searched={searched}
          selected={selected}
          onSelect={setSelected}
        />
      )}

      {results?.length > 0 && (
        <Card>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex min-w-0 flex-1 flex-col gap-2" style={mutedTextStyle}>
              Channel
              <Input as="select" value={channel} onChange={(event) => setChannel(event.target.value)}>
                {CHANNELS.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </Input>
            </label>
            <Button variant="primary" disabled={busy || !selected} onClick={download}>
              Download log
            </Button>
          </div>
        </Card>
      )}

      {notice && <CatalogNoticeBar notice={notice} onDismiss={() => setNotice(null)} />}
    </div>
  )
}

/**
 * The accounts a search found, as a radio group: exactly one is downloaded.
 * The hand-rolled `ul` in a flush `Card` the other admin listings use.
 */
function AccountList({ results, searched, selected, onSelect }) {
  const headingId = React.useId()

  if (results.length === 0) {
    return <p style={mutedTextStyle}>{`No account matches “${searched}”.`}</p>
  }

  return (
    <section className="flex flex-col gap-3">
      <h2 id={headingId} style={headingStyle}>
        Accounts
      </h2>
      <Card style={{ padding: 0 }}>
        <ul role="radiogroup" aria-labelledby={headingId} className="m-0 list-none p-0">
          {results.map((user, i) => (
            <li
              key={user.id}
              style={{ borderTop: i === 0 ? 'none' : '1px solid var(--border-default)' }}
            >
              {/* The whole row is the label, so it is a full-width tap target. */}
              <label className="flex min-h-[44px] cursor-pointer items-center gap-3 px-4 py-3">
                <input
                  type="radio"
                  name="log-account"
                  checked={selected?.id === user.id}
                  onChange={() => onSelect(user)}
                />
                <span className="min-w-0 flex-1">
                  <span
                    className="block"
                    style={{
                      fontFamily: 'var(--font-display)',
                      fontWeight: 'var(--weight-semibold)',
                      fontSize: 'var(--text-sm)',
                      color: 'var(--text-strong)',
                      overflowWrap: 'anywhere',
                    }}
                  >
                    {user.email}
                  </span>
                  <span className="block" style={{ fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}>
                    {user.username ? `@${user.username}` : 'No handle'}
                  </span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      </Card>
    </section>
  )
}
