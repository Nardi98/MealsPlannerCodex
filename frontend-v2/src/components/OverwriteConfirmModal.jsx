import React from 'react'
import { Card, Button } from './'
import { ModalScrim } from './Modal'
import { Z } from '../lib/layers'

export default function OverwriteConfirmModal({
  onCancel,
  onConfirm,
  title = 'Overwrite Existing Data',
  message = 'This will overwrite existing data. Are you sure?',
  items = [],
}) {
  return (
    <ModalScrim z={Z.nested}>
      <Card className="space-y-4 w-full max-w-md" style={{ color: 'var(--text-strong)' }}>
        <h3 className="text-lg font-medium">{title}</h3>
        <div className="space-y-2 text-sm">
          <p>{message}</p>
          {items.length > 0 && (
            <div className="rounded-lg border p-2" style={{ borderColor: 'var(--border)' }}>
              <p className="mb-1 font-medium">Affected:</p>
              <ul className="list-disc list-inside space-y-1 text-left">
                {items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button variant="danger" onClick={onConfirm}>Overwrite</Button>
        </div>
      </Card>
    </ModalScrim>
  )
}

