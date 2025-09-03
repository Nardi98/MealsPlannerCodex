import React from 'react'
import { Button, Input } from './'
import { FunnelIcon, ChevronDownIcon } from '@heroicons/react/24/outline'

export default function MealActionModal({ date, meal='lunch', onAccept, onReject }) {
  const [open, setOpen] = React.useState(false)

  const dt = new Date(date)
  const dateStr = dt.toLocaleDateString(undefined, { month: 'long', day: 'numeric' })
  const weekday = dt.toLocaleDateString(undefined, { weekday: 'long' })
  const mealName = meal === 'dinner' ? 'Dinner' : 'Lunch'

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[60]">
      <div className="bg-white rounded-2xl p-6 w-full max-w-md space-y-4" style={{ color: 'var(--text-strong)' }}>
        <h3 className="text-lg font-medium">{`${weekday}, ${dateStr} — ${mealName}`}</h3>
        <div className="flex justify-end gap-2">
          <Button variant="danger" onClick={onReject}>Reject</Button>
          <Button variant="a1" onClick={onAccept}>Accept</Button>
        </div>
        <div className="border-t pt-4" style={{ borderColor: 'var(--border)' }}>
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="w-full flex justify-between items-center"
          >
            <span className="font-medium">Swap</span>
            <ChevronDownIcon className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} />
          </button>
          {open && (
            <div className="mt-4 space-y-2">
              <div className="flex items-center gap-2">
                <Input placeholder="Search recipes..." className="flex-1" />
                <FunnelIcon className="h-5 w-5" />
              </div>
              <div className="mt-2 max-h-40 overflow-y-auto border rounded-xl p-2" style={{ borderColor: 'var(--border)' }}>
                {/* Recipe list container */}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

