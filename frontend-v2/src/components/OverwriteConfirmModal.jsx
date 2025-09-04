import React from 'react'
import { Card, Button } from './'

export default function OverwriteConfirmModal({ onCancel, onConfirm }) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[70]">
      <Card className="space-y-4 w-full max-w-md" style={{ color: 'var(--text-strong)' }}>
        <h3 className="text-lg font-medium">Overwrite Existing Data</h3>
        <p className="text-sm">This will overwrite existing data. Are you sure?</p>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button variant="danger" onClick={onConfirm}>Overwrite</Button>
        </div>
      </Card>
    </div>
  )
}

