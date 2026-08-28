import React from 'react'
import { Button, IconButton, Input, TagSelector } from './'
import {
  FunnelIcon,
  ChevronDownIcon,
  XMarkIcon,
  NoSymbolIcon,
  TrashIcon,
} from '@heroicons/react/24/outline'
import { recipesApi } from '../api/recipesApi'
import { tagsApi } from '../api/tagsApi'
import { ModalScrim } from './Modal'

export default function MealActionModal({
  date,
  meal = 'lunch',
  recipe,
  sides = [],
  accepted = false,
  onAccept,
  onReject,
  onSwap,
  onClose,
  onAddSide,
  onRejectSide,
  onRemoveSide,
  onSwapSide,
}) {
  const [open, setOpen] = React.useState(false)
  const [sideSwapOpen, setSideSwapOpen] = React.useState(false)
  const [recipes, setRecipes] = React.useState([])
  const [tags, setTags] = React.useState([])
  const [query, setQuery] = React.useState('')
  const [tagFilterOpen, setTagFilterOpen] = React.useState(false)
  const [selectedTags, setSelectedTags] = React.useState([])
  const [sideQuery, setSideQuery] = React.useState('')
  const [sideTagFilterOpen, setSideTagFilterOpen] = React.useState(false)
  const [sideSelectedTags, setSideSelectedTags] = React.useState([])
  const [selectedSideIndex, setSelectedSideIndex] = React.useState(0)

  React.useEffect(() => {
    async function load() {
      try {
        const [r, t] = await Promise.all([
          recipesApi.fetchAll(),
          tagsApi.fetchAll(),
        ])
        setRecipes(r)
        setTags(t.map((tag) => (tag.name ? tag.name : tag)))
      } catch (err) {
        console.error('Failed to load recipes or tags', err)
      }
    }
    load()
  }, [])

  const filtered = React.useMemo(
    () =>
      recipes.filter((r) => {
        if (r.course === 'side') return false
        const matchesQuery = r.title
          .toLowerCase()
          .includes(query.toLowerCase())
        const matchesTags = selectedTags.every((t) => r.tags?.includes(t))
        return matchesQuery && matchesTags
      }),
    [recipes, query, selectedTags]
  )

  const sideFiltered = React.useMemo(
    () =>
      recipes.filter((r) => {
        if (r.course !== 'side') return false
        if (r.title === recipe) return false
        if (sides.includes(r.title)) return false
        const matchesQuery = r.title
          .toLowerCase()
          .includes(sideQuery.toLowerCase())
        const matchesTags = sideSelectedTags.every((t) => r.tags?.includes(t))
        return matchesQuery && matchesTags
      }),
    [recipes, sideQuery, sideSelectedTags, sides, recipe]
  )

  const handleSwapClick = (title) => {
    if (onSwap) onSwap(title)
  }

  const handleSwapSideClick = (title) => {
    if (onSwapSide) onSwapSide(selectedSideIndex, title)
  }

  const dt = new Date(date)
  const dateStr = dt.toLocaleDateString(undefined, { month: 'long', day: 'numeric' })
  const weekday = dt.toLocaleDateString(undefined, { weekday: 'long' })
  const mealName = meal === 'dinner' ? 'Dinner' : 'Lunch'

  return (
    <ModalScrim>
      <div
        className="relative bg-white rounded-2xl p-4 md:p-6 w-full max-w-lg space-y-4"
        style={{
          color: 'var(--text-strong)',
          // Own the scroll rather than relying on the scrim, matching `Modal`.
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
      >
        <IconButton
          Icon={XMarkIcon}
          label="Close"
          onClick={onClose}
          className="absolute top-2 right-2"
        />
        <h3 className="text-lg font-medium pr-12">{`${weekday}, ${dateStr} — ${mealName}`}</h3>
        <div className="flex items-center justify-between">
          <div className="font-medium">{recipe}</div>
          <Button variant="danger" onClick={() => onReject?.()}>
            Reject
          </Button>
        </div>
        <div className="mt-2">
          <Button onClick={onAddSide}>Add side dish</Button>
        </div>
        {sides.length > 0 && (
          <div className="mt-2 space-y-1">
            {sides.map((s, i) => (
              <div
                key={i}
                className="flex items-center justify-between gap-2 text-sm"
              >
                <span className="min-w-0">{s}</span>
                <div className="flex shrink-0 gap-1">
                  <IconButton
                    Icon={NoSymbolIcon}
                    label={`Reject side dish ${s}`}
                    onClick={() => onRejectSide?.(i)}
                  />
                  <IconButton
                    Icon={TrashIcon}
                    label={`Remove side dish ${s}`}
                    onClick={() => onRemoveSide?.(i)}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
        {!accepted && (
          <Button
            variant="a1"
            onClick={() => onAccept?.()}
            className="mt-4"
          >
            Accept
          </Button>
        )}
        <div className="border-t pt-4" style={{ borderColor: 'var(--border)' }}>
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="min-h-11 w-full flex justify-between items-center"
          >
            <span className="font-medium">Swap</span>
            <ChevronDownIcon
              className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`}
            />
          </button>
          {open && (
            <div className="mt-4 space-y-2">
              <div className="flex items-center gap-2">
                <Input
                  placeholder="Search recipes..."
                  className="flex-1"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <IconButton
                  Icon={FunnelIcon}
                  label="Filter recipes by tag"
                  onClick={() => setTagFilterOpen((o) => !o)}
                />
              </div>
              {tagFilterOpen && (
                <TagSelector
                  tags={tags}
                  selected={selectedTags}
                  onChange={setSelectedTags}
                />
              )}
              <div
                className="mt-2 max-h-64 overflow-y-auto border rounded-xl p-2"
                style={{ borderColor: 'var(--border)' }}
              >
                {filtered.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    className="flex min-h-11 w-full items-center rounded px-2 text-left hover:bg-gray-100 focus:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
                    onClick={() => handleSwapClick(r.title)}
                  >
                    {r.title}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="border-t pt-4" style={{ borderColor: 'var(--border)' }}>
          <button
            type="button"
            onClick={() => setSideSwapOpen((o) => !o)}
            className="min-h-11 w-full flex justify-between items-center"
          >
            <span className="font-medium">Swap side dish</span>
            <ChevronDownIcon
              className={`h-4 w-4 transition-transform ${sideSwapOpen ? 'rotate-180' : ''}`}
            />
          </button>
          {sideSwapOpen && (
            <div className="mt-4 space-y-2">
              {sides.length > 0 && (
                <select
                  className="min-h-11 w-full border rounded px-2 py-1"
                  style={{ borderColor: 'var(--border)' }}
                  value={selectedSideIndex}
                  onChange={(e) => setSelectedSideIndex(parseInt(e.target.value))}
                >
                  {sides.map((s, i) => (
                    <option key={i} value={i}>
                      {s}
                    </option>
                  ))}
                </select>
              )}
              <div className="flex items-center gap-2">
                <Input
                  placeholder="Search recipes..."
                  className="flex-1"
                  value={sideQuery}
                  onChange={(e) => setSideQuery(e.target.value)}
                />
                <IconButton
                  Icon={FunnelIcon}
                  label="Filter side dishes by tag"
                  onClick={() => setSideTagFilterOpen((o) => !o)}
                />
              </div>
              {sideTagFilterOpen && (
                <TagSelector
                  tags={tags}
                  selected={sideSelectedTags}
                  onChange={setSideSelectedTags}
                />
              )}
              <div
                className="mt-2 max-h-64 overflow-y-auto border rounded-xl p-2"
                style={{ borderColor: 'var(--border)' }}
              >
                {sideFiltered.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    className="flex min-h-11 w-full items-center rounded px-2 text-left hover:bg-gray-100 focus:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
                    onClick={() => handleSwapSideClick(r.title)}
                  >
                    {r.title}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </ModalScrim>
  )
}

