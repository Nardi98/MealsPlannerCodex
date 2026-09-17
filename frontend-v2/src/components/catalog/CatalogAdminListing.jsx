import React from 'react'
import { Badge } from '../Badge'
import { Button } from '../Button'
import { Card } from '../Card'
import { mutedTextStyle } from './textStyles'

const STATUS = {
  published: { label: 'Published', tone: 'forest' },
  retired: { label: 'Retired', tone: 'caramel' },
}

/**
 * Every catalog entry, published and retired, from the admin endpoint (UI-16).
 *
 * Deliberately a separate view over a separate request: retired entries are
 * never folded into the browse grid, which hides them from admins too (RET-1).
 * Each row offers Edit and exactly one of Publish or Retire. There is no
 * delete: retiring is the only way out of the library (RET-5).
 *
 * `rows` is null until the first load lands.
 */
export default function CatalogAdminListing({ rows, onEdit, onPublish, onRetire }) {
  const headingId = React.useId()

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2
          id={headingId}
          style={{ margin: 0, fontSize: 'var(--text-lg)', color: 'var(--text-strong)' }}
        >
          All library entries
        </h2>
        <p style={{ ...mutedTextStyle, marginTop: 4 }}>
          Retired entries are hidden from Discover for everyone, you included. Publishing one
          brings it back with its count intact.
        </p>
      </div>

      {rows === null && <p style={mutedTextStyle}>Loading the library entries…</p>}
      {rows !== null && rows.length === 0 && <p style={mutedTextStyle}>The library has no entries yet.</p>}

      {rows !== null && rows.length > 0 && (
        <Card style={{ padding: 0 }}>
          <ul aria-labelledby={headingId} className="m-0 list-none p-0">
            {rows.map((recipe, i) => {
              const status = STATUS[recipe.status] || STATUS.published
              const count = recipe.adoption_count ?? 0
              return (
                <li
                  key={recipe.id}
                  className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3"
                  style={{ borderTop: i === 0 ? 'none' : '1px solid var(--border-default)' }}
                >
                  <div className="min-w-0 flex-1">
                    <div
                      style={{
                        fontFamily: 'var(--font-display)',
                        fontWeight: 'var(--weight-semibold)',
                        fontSize: 'var(--text-sm)',
                        color: 'var(--text-strong)',
                      }}
                    >
                      {recipe.title}
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}>
                      {`${recipe.course} · added ${count} ${count === 1 ? 'time' : 'times'}`}
                    </div>
                  </div>
                  <Badge tone={status.tone}>{status.label}</Badge>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button variant="ghost" onClick={() => onEdit(recipe)}>
                      Edit
                    </Button>
                    {recipe.status === 'retired' ? (
                      <Button variant="secondary" onClick={() => onPublish(recipe)}>
                        Publish
                      </Button>
                    ) : (
                      <Button variant="ghost" onClick={() => onRetire(recipe)}>
                        Retire
                      </Button>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        </Card>
      )}
    </section>
  )
}
