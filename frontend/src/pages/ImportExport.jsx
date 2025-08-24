import React, { useContext, useState } from 'react'
import { AppContext } from '../App'

export default function ImportExport() {
  const { recipes, plan, setRecipes, setPlan } = useContext(AppContext)
  const [exportData, setExportData] = useState('')

  const handleExport = () => {
    const data = { recipes, plan }
    const json = JSON.stringify(data, null, 2)
    setExportData(json)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'mealplanner_data.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleImport = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target.result)
        setRecipes(data.recipes || [])
        setPlan(data.plan || {})
      } catch {
        alert('Invalid JSON file')
      }
    }
    reader.readAsText(file)
  }

  return (
    <div>
      <h1>Import / Export</h1>
      <div>
        <button type="button" onClick={handleExport}>Export Data</button>
      </div>
      {exportData && (
        <div>
          <h3>Exported JSON</h3>
          <textarea value={exportData} readOnly rows={10} cols={50} />
        </div>
      )}
      <div>
        <h3>Import Data</h3>
        <input type="file" accept="application/json" onChange={handleImport} />
      </div>
    </div>
  )
}
