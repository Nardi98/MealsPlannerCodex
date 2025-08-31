import React from 'react'
import { Button, Badge, Card, NavItem, Input } from '../ui'
import {
  CheckCircleIcon,
  XCircleIcon,
  TagIcon,
  ArrowsRightLeftIcon,
  AdjustmentsHorizontalIcon,
  BookOpenIcon,
} from '@heroicons/react/24/outline'

export default function UiPreview() {
  return (
    <div className="space-y-4 p-4">
      <Card>
        <div className="mb-2 text-sm text-[var(--text-subtle)]">Buttons</div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="primary" Icon={CheckCircleIcon}>Accept</Button>
          <Button variant="danger" Icon={XCircleIcon}>Reject</Button>
          <Button variant="a1" Icon={TagIcon}>Edit</Button>
          <Button variant="a2" Icon={ArrowsRightLeftIcon}>Swap</Button>
          <Button variant="ghost" Icon={AdjustmentsHorizontalIcon}>Ghost</Button>
        </div>
      </Card>

      <Card>
        <div className="mb-2 text-sm text-[var(--text-subtle)]">Badges</div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="a3">pasta</Badge>
          <Badge tone="a1">leftovers</Badge>
          <Badge tone="a2">highlight</Badge>
        </div>
      </Card>

      <Card>
        <div className="mb-2 text-sm text-[var(--text-subtle)]">Nav Items</div>
        <div className="grid grid-cols-1 gap-2">
          <NavItem active Icon={BookOpenIcon} label="Recipes" />
          <NavItem Icon={TagIcon} label="Tags" />
        </div>
      </Card>

      <Card>
        <div className="mb-2 text-sm text-[var(--text-subtle)]">Inputs</div>
        <div className="grid grid-cols-1 gap-2">
          <Input placeholder="Search" />
          <Input placeholder="Type something…" />
        </div>
      </Card>
    </div>
  )
}
