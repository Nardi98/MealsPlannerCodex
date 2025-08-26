import React, { useContext, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppContext } from '../App'
import { request } from '../api/client'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export default function ImportExport() {
  const { setRecipes, setPlan } = useContext(AppContext)
  const [exportData, setExportData] = useState('')
  const [mode, setMode] = useState('overwrite')
  const [fileData, setFileData] = useState(null)
  const [duplicates, setDuplicates] = useState([])
  const navigate = useNavigate()

  const handleExport = async () => {
    const resp = await fetch(`${API_BASE_URL}/data/export`)
    const json = await resp.text()
    setExportData(json)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'mealplanner_data.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = async (ev) => {
      try {
        const data = JSON.parse(ev.target.result)
        setFileData(data)
        if (mode === 'merge') {
          const existing = await request('/recipes')
          const existingTitles = new Map(existing.map((r) => [r.title, r.id]))
          const dup = (data.recipes || [])
            .filter((r) => existingTitles.has(r.title))
            .map((r) => ({ title: r.title, id: existingTitles.get(r.title), action: 'keep_both' }))
          setDuplicates(dup)
        } else {
          setDuplicates([])
        }
      } catch {
        alert('Invalid JSON file')
      }
    }
    reader.readAsText(file)
  }

  const updateDup = (title, action) => {
    setDuplicates(duplicates.map((d) => (d.title === title ? { ...d, action } : d)))
  }

  const doImport = async () => {
    if (!fileData) return
    if (mode === 'overwrite' && !window.confirm('This will delete existing data. Continue?')) return
    const payload = JSON.parse(JSON.stringify(fileData))
    for (const d of duplicates) {
      if (d.action === 'keep_old') {
        payload.recipes = payload.recipes.filter((r) => r.title !== d.title)
      } else if (d.action === 'keep_new') {
        await request(`/recipes/${d.id}`, { method: 'DELETE' })
      }
    }
    try {
      await request(`/data/import?mode=${mode}`, {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      const newRecipes = await request('/recipes')
      const planResp = await request('/plan')
      const titlePlan = {}
      if (planResp && typeof planResp === 'object') {
        Object.entries(planResp).forEach(([day, meals]) => {
          titlePlan[day] = meals.map((m) => m.recipe || m.title || m)
        })
      }
      setRecipes(newRecipes)
      setPlan(titlePlan)
      navigate('/')
    } catch (err) {
      alert(`Import failed: ${err.message}`)
    }
  }

  const handleDelete = async () => {
    if (!window.confirm('This will permanently delete all data. Continue?')) return
    try {
      await request('/data', { method: 'DELETE' })
      setRecipes([])
      setPlan({})
      navigate('/')
    } catch (err) {
      alert(`Delete failed: ${err.message}`)
    }
  }

  return (
    <div>
      <h1>Import / Export</h1>
      <div>
        <button type="button" onClick={handleExport}>Export Data</button>
      </div>
      <div>
        <button type="button" onClick={handleDelete}>Delete All Data</button>
      </div>
      {exportData && (
        <div>
          <h3>Exported JSON</h3>
          <textarea value={exportData} readOnly rows={10} cols={50} />
        </div>
      )}
      <div>
        <h3>Import Data</h3>
        <label>
          <input type="radio" value="overwrite" checked={mode === 'overwrite'} onChange={(e) => setMode(e.target.value)} /> Overwrite
        </label>
        <label>
          <input type="radio" value="merge" checked={mode === 'merge'} onChange={(e) => setMode(e.target.value)} /> Merge
        </label>
        <div>
          <input type="file" accept="application/json" onChange={handleFile} />
        </div>
        {duplicates.length > 0 && (
          <div>
            <h4>Resolve Duplicates</h4>
            {duplicates.map((d) => (
              <div key={d.title}>
                <span>{`Recipe '${d.title}' exists already:`}</span>
                <select value={d.action} onChange={(e) => updateDup(d.title, e.target.value)}>
                  <option value="keep_old">keep old</option>
                  <option value="keep_new">keep new</option>
                  <option value="keep_both">keep both</option>
                </select>
              </div>
            ))}
          </div>
        )}
        <button type="button" onClick={doImport} disabled={!fileData}>Import</button>
      </div>
    </div>
  )
}
