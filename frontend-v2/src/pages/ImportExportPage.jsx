import React from 'react'
import { Card, Button, Input } from '../components'
import { dataApi } from '../api/dataApi'

export default function ImportExportPage() {
  const [file, setFile] = React.useState(null)
  const [mode, setMode] = React.useState('merge')

  const handleExport = async () => {
    try {
      const data = await dataApi.exportDatabase()
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: 'application/json',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'meal-planner-export.json'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Failed to export database', err)
      alert(`Failed to export database: ${err.message}`)
    }
  }

  const handleFileChange = (e) => {
    const f = e.target.files && e.target.files[0]
    setFile(f || null)
  }

  return (
    <div className="space-y-4">
      <Card className="space-y-3">
        <div>
          <h2 className="text-lg font-medium" style={{ color: 'var(--text-strong)' }}>
            Export Database
          </h2>
          <p className="text-sm text-[color:var(--text-subtle)]">
            Download a JSON backup of your meal planner data.
          </p>
        </div>
        <Button onClick={handleExport}>Export Database</Button>
      </Card>

      <Card className="space-y-3">
        <div>
          <h2 className="text-lg font-medium" style={{ color: 'var(--text-strong)' }}>
            Import Database
          </h2>
          <p className="text-sm text-[color:var(--text-subtle)]">
            Choose a backup file to import.
          </p>
        </div>
        <Input type="file" onChange={handleFileChange} />
        <select
          className="rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
          style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
          value={mode}
          onChange={(e) => setMode(e.target.value)}
        >
          <option value="merge">Merge</option>
          <option value="overwrite">Overwrite</option>
        </select>
        {file && <Button>Import</Button>}
      </Card>
    </div>
  )
}

