import React from 'react'
import { Button, Input, TagSelector } from './'
import {
  FunnelIcon,
  ChevronDownIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { recipesApi } from '../api/recipesApi'
import { tagsApi } from '../api/tagsApi'

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
}) {
  const [open, setOpen] = React.useState(false)
  const [recipes, setRecipes] = React.useState([])
  const [tags, setTags] = React.useState([])
  const [query, setQuery] = React.useState('')
  const [tagFilterOpen, setTagFilterOpen] = React.useState(false)
  const [selectedTags, setSelectedTags] = React.useState([])

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
        const matchesQuery = r.title
          .toLowerCase()
          .includes(query.toLowerCase())
        const matchesTags = selectedTags.every((t) => r.tags?.includes(t))
        return matchesQuery && matchesTags
      }),
    [recipes, query, selectedTags]
  )

  const handleSwapClick = (title) => {
    if (onSwap) onSwap(title)
    if (onClose) onClose()
  }

  const dt = new Date(date)
  const dateStr = dt.toLocaleDateString(undefined, { month: 'long', day: 'numeric' })
  const weekday = dt.toLocaleDateString(undefined, { weekday: 'long' })
  const mealName = meal === 'dinner' ? 'Dinner' : 'Lunch'

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[60]">
      <div
        className="relative bg-white rounded-2xl p-6 w-full max-w-md space-y-4"
        style={{ color: 'var(--text-strong)' }}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4"
        >
          <XMarkIcon className="h-5 w-5" />
        </button>
        <h3 className="text-lg font-medium pr-8">{`${weekday}, ${dateStr} — ${mealName}`}</h3>
        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium">{recipe}</div>
            {sides.length > 0 && (
              <div className="text-sm">{sides.join(', ')}</div>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="danger" onClick={onReject}>
              Reject
            </Button>
            {!accepted && (
              <Button variant="a1" onClick={onAccept}>
                Accept
              </Button>
            )}
          </div>
        </div>
        <div className="border-t pt-4" style={{ borderColor: 'var(--border)' }}>
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="w-full flex justify-between items-center"
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
                <FunnelIcon
                  className="h-5 w-5 cursor-pointer"
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
                className="mt-2 max-h-40 overflow-y-auto border rounded-xl p-2"
                style={{ borderColor: 'var(--border)' }}
              >
                {filtered.map((r) => (
                  <div
                    key={r.id}
                    className="p-1 cursor-pointer hover:bg-gray-100 rounded"
                    onClick={() => handleSwapClick(r.title)}
                  >
                    {r.title}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

