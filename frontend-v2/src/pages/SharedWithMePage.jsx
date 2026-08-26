import React from 'react'
import { InboxArrowDownIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { Badge, Button, Card, Modal, AttributionLine } from '../components'
import { sharedWithMeApi } from '../api/sharedWithMeApi'

// Recipes other people addressed to this account (SWM-1 / SWM-2 / SWM-3).
//
// Deliberately kept apart from `recipesApi` state (SWM-5): a shared recipe must
// not reach the user's recipe list, planner candidates, or shopping list until
// it has been explicitly copied, so nothing here is ever merged into the recipe
// collection.
//
// Everything rendered comes from the backend's PRV-2 allowlist — title, image,
// procedure, ingredients, tags, course, the author's display name and handle,
// and the attribution snapshot. Fields outside that list are not read,
// so a future column cannot leak by being added upstream.

// The share list holds no raw tokens (SH-3 stores them hashed), so nothing here
// can be pasted anywhere; entries are addressed by `share_id` alone.

const NEUTRAL_GONE =
  'This recipe is no longer available. The person who shared it may have ' +
  'revoked the link, or it may have expired.'

// SH-22 / the 404 contract: revoked, expired, dismissed, and never-existed are
// one indistinguishable answer, so it is presented calmly rather than as a
// failure implying the recipe is still there.
//
// The status alone decides. `client.js` attaches it to every error it throws,
// and it is the part of the response the backend has actually promised —
// unlike the `detail` prose, which is free to be reworded or translated, and
// which would have made a 500 mentioning "not found" look like a gone recipe.
function isGone(error) {
  return error?.status === 404
}

// AttributionLine's prop shape is frozen around `source_*`; shared entries carry
// the same snapshot under `attribution`. Mapped rather than duplicated so the
// credit renders identically wherever the recipe appears (AT-3 / AT-8).
//
// The two shapes were considered for reconciliation and deliberately kept
// apart. They are not an accident: `RecipeOut.source_*` is a flat mirror of the
// recipe's own columns, which is what an owner's recipe payload should be,
// while `PublicRecipe.attribution` is a nested snapshot object because the
// public page renders it as a *block* that is present or absent as a unit —
// `blocks.py` drops the attribution block on `attribution is None`, and the
// Jinja templates read `attribution.recipe_title`. Collapsing either into the
// other would put `source_` prefixes inside a namespace already called
// "attribution", or flatten a nullable group into six loose nullable fields and
// lose the "present as a unit" check the block rendering depends on. The cost
// of reconciling is two schemas, two templates, and their tests; the cost of
// not reconciling is the six lines below. The six lines win.
function asAttributionRecipe(recipe) {
  const a = recipe?.attribution
  if (!a) return null
  return {
    source_author_username: a.author_username,
    source_recipe_title: a.recipe_title,
    copied_at: a.copied_at ?? null,
  }
}

function formatQuantity(ingredient) {
  const parts = []
  if (ingredient.quantity !== null && ingredient.quantity !== undefined) {
    parts.push(String(ingredient.quantity))
  }
  if (ingredient.unit) parts.push(ingredient.unit)
  return parts.join(' ')
}

function SharedCard({ entry, onOpen, onDismiss, dismissing }) {
  const { recipe } = entry
  const attribution = asAttributionRecipe(recipe)

  return (
    <Card style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <button
        type="button"
        onClick={() => onOpen(entry)}
        aria-label={`View ${recipe.title}`}
        className="text-left"
        style={{
          background: 'none',
          border: 'none',
          padding: 0,
          cursor: 'pointer',
          width: '100%',
          flex: 1,
        }}
      >
        {recipe.image_url ? (
          <img
            src={recipe.image_url}
            alt=""
            style={{ width: '100%', height: 140, objectFit: 'cover', display: 'block' }}
          />
        ) : (
          <div
            style={{
              height: 140,
              background: 'var(--surface-sunken)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <InboxArrowDownIcon
              className="h-8 w-8"
              style={{ color: 'var(--cat-sky)', opacity: 0.6 }}
            />
          </div>
        )}
        <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <h2
            style={{
              margin: 0,
              fontFamily: 'var(--font-display)',
              fontSize: 'var(--text-base)',
              fontWeight: 'var(--weight-semibold)',
              color: 'var(--text-strong)',
            }}
          >
            {recipe.title}
          </h2>
          <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}>
            {`Shared by ${recipe.author_display_name} · @${recipe.author_username}`}
          </p>
          {attribution && <AttributionLine recipe={attribution} />}
          <div className="flex flex-wrap items-center gap-1">
            <Badge tone="sky">{recipe.course}</Badge>
            {(recipe.tags || []).map((tag) => (
              <Badge key={tag} tone="olive">
                {tag}
              </Badge>
            ))}
          </div>
        </div>
      </button>
      <div
        style={{
          padding: '0 16px 16px',
          display: 'flex',
          justifyContent: 'flex-end',
        }}
      >
        <Button
          variant="ghost"
          size="sm"
          Icon={XMarkIcon}
          disabled={dismissing}
          onClick={() => onDismiss(entry)}
          aria-label={`Dismiss ${recipe.title}`}
        >
          Dismiss
        </Button>
      </div>
    </Card>
  )
}

function SharedRecipeDetail({ entry, onClose, onCopy, copying, copyResult, copyError }) {
  const { recipe } = entry
  const attribution = asAttributionRecipe(recipe)

  return (
    <Modal title={recipe.title} onClose={onClose} maxWidth={640}>
      <div className="flex flex-col gap-4">
        <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--text-subtle)' }}>
          {`Shared by ${recipe.author_display_name} · @${recipe.author_username}`}
        </p>
        {attribution && <AttributionLine recipe={attribution} />}

        {recipe.image_url && (
          <img
            src={recipe.image_url}
            alt=""
            style={{
              width: '100%',
              maxHeight: 260,
              objectFit: 'cover',
              borderRadius: 'var(--radius-md)',
            }}
          />
        )}

        <div className="flex flex-wrap items-center gap-1">
          <Badge tone="sky">{recipe.course}</Badge>
          {(recipe.tags || []).map((tag) => (
            <Badge key={tag} tone="olive">
              {tag}
            </Badge>
          ))}
        </div>

        <section>
          <h4
            style={{
              margin: '0 0 8px',
              fontFamily: 'var(--font-display)',
              fontSize: 'var(--text-sm)',
              fontWeight: 'var(--weight-semibold)',
              color: 'var(--text-strong)',
            }}
          >
            Ingredients
          </h4>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 'var(--text-sm)' }}>
            {(recipe.ingredients || []).map((ing, i) => (
              <li key={`${ing.name}-${i}`} style={{ color: 'var(--text-muted)' }}>
                {formatQuantity(ing) ? `${ing.name} — ${formatQuantity(ing)}` : ing.name}
              </li>
            ))}
          </ul>
        </section>

        {recipe.procedure && (
          <section>
            <h4
              style={{
                margin: '0 0 8px',
                fontFamily: 'var(--font-display)',
                fontSize: 'var(--text-sm)',
                fontWeight: 'var(--weight-semibold)',
                color: 'var(--text-strong)',
              }}
            >
              Method
            </h4>
            {/* Author-controlled text: rendered as text, never as markup. */}
            <p
              style={{
                margin: 0,
                whiteSpace: 'pre-wrap',
                fontSize: 'var(--text-sm)',
                color: 'var(--text-muted)',
              }}
            >
              {recipe.procedure}
            </p>
          </section>
        )}

        {copyResult && (
          <p
            role="status"
            style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--c-pos)' }}
          >
            {copyResult.already_copied
              ? `You already had a copy of ${copyResult.title}; a second one has been added to your recipes.`
              : `${copyResult.title} has been added to your recipes.`}
          </p>
        )}
        {copyError && (
          <p
            role={isGone(copyError) ? 'status' : 'alert'}
            style={{
              margin: 0,
              fontSize: 'var(--text-sm)',
              color: isGone(copyError) ? 'var(--text-muted)' : 'var(--c-neg)',
            }}
          >
            {isGone(copyError) ? NEUTRAL_GONE : copyError.message}
          </p>
        )}

        {/* SWM-2: view and copy are the only permitted actions. */}
        <div className="flex justify-end">
          <Button variant="accent" disabled={copying} onClick={() => onCopy(entry)}>
            {copying ? 'Copying…' : 'Copy to my book'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export function SharedWithMePage() {
  const [entries, setEntries] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState(null)
  const [openId, setOpenId] = React.useState(null)
  const [dismissingId, setDismissingId] = React.useState(null)
  const [copying, setCopying] = React.useState(false)
  const [copyResult, setCopyResult] = React.useState(null)
  const [copyError, setCopyError] = React.useState(null)

  React.useEffect(() => {
    let cancelled = false
    sharedWithMeApi
      .fetchAll()
      .then((rows) => {
        if (!cancelled) setEntries(Array.isArray(rows) ? rows : [])
      })
      .catch((err) => {
        if (!cancelled) setError(err)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const open = entries.find((e) => e.share_id === openId) || null

  const handleOpen = (entry) => {
    setOpenId(entry.share_id)
    setCopyResult(null)
    setCopyError(null)
  }

  const handleClose = () => {
    setOpenId(null)
    setCopyResult(null)
    setCopyError(null)
  }

  const handleCopy = async (entry) => {
    setCopying(true)
    setCopyResult(null)
    setCopyError(null)
    try {
      setCopyResult(await sharedWithMeApi.copy(entry.share_id))
    } catch (err) {
      setCopyError(err)
    } finally {
      setCopying(false)
    }
  }

  const handleDismiss = async (entry) => {
    setDismissingId(entry.share_id)
    try {
      await sharedWithMeApi.dismiss(entry.share_id)
      // SWM-3 is recipient-side only: the share itself keeps working, so the
      // entry is dropped locally rather than re-fetched.
      setEntries((rows) => rows.filter((r) => r.share_id !== entry.share_id))
      setOpenId((id) => (id === entry.share_id ? null : id))
    } catch (err) {
      setError(err)
    } finally {
      setDismissingId(null)
    }
  }

  return (
    <section>
      <h1
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: 'var(--text-2xl)',
          fontWeight: 'var(--weight-semibold)',
          color: 'var(--text-strong)',
          margin: 0,
        }}
      >
        Shared with me
      </h1>
      <p style={{ marginTop: 4, color: 'var(--text-subtle)', fontSize: 'var(--text-sm)' }}>
        Read-only until you copy one into your own recipes.
      </p>

      {error && (
        <p
          role="alert"
          style={{ marginTop: 16, color: 'var(--c-neg)', fontSize: 'var(--text-sm)' }}
        >
          {isGone(error) ? NEUTRAL_GONE : error.message}
        </p>
      )}

      {loading && (
        <p style={{ marginTop: 16, color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
          Loading…
        </p>
      )}

      {!loading && !error && entries.length === 0 && (
        <p style={{ marginTop: 16, color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
          Nothing has been shared with you yet.
        </p>
      )}

      {entries.length > 0 && (
        <div className="card-grid" style={{ marginTop: 20 }}>
          {entries.map((entry) => (
            <SharedCard
              key={entry.share_id}
              entry={entry}
              onOpen={handleOpen}
              onDismiss={handleDismiss}
              dismissing={dismissingId === entry.share_id}
            />
          ))}
        </div>
      )}

      {open && (
        <SharedRecipeDetail
          entry={open}
          onClose={handleClose}
          onCopy={handleCopy}
          copying={copying}
          copyResult={copyResult}
          copyError={copyError}
        />
      )}
    </section>
  )
}

export default SharedWithMePage
