import React from 'react'
import {
  Card,
  Button,
  Input,
  OverwriteConfirmModal,
  MergeConflictModal,
} from '../components'
import { dataApi } from '../api/dataApi'
import { recipesApi } from '../api/recipesApi'
import { ingredientsApi } from '../api/ingredientsApi'

export default function ImportExportPage() {
  const [file, setFile] = React.useState(null)
  const [parsedData, setParsedData] = React.useState(null)
  const [mode, setMode] = React.useState('merge')
  const [showOverwriteModal, setShowOverwriteModal] = React.useState(false)
  const [mergeConflicts, setMergeConflicts] = React.useState(null)
  const [existingRecipes, setExistingRecipes] = React.useState([])
  const [existingIngredients, setExistingIngredients] = React.useState([])
  const fileInputRef = React.useRef(null)

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

  const handleFileChange = async (e) => {
    const f = e.target.files && e.target.files[0]
    setFile(f || null)
    setParsedData(null)
    if (f) {
      try {
        const text = await f.text()
        setParsedData(JSON.parse(text))
      } catch (err) {
        console.error('Failed to parse JSON', err)
        alert('Selected file is not valid JSON')
      }
    }
  }

  const clearFile = () => {
    setFile(null)
    setParsedData(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleImport = async () => {
    if (!file || !parsedData) return
    if (mode === 'overwrite') {
      setShowOverwriteModal(true)
      return
    }

    try {
      const [existingRecs, existingIngs] = await Promise.all([
        recipesApi.fetchAll(),
        ingredientsApi.fetchAll(),
      ])
      const recipeTitles = new Set(existingRecs.map((r) => r.title.toLowerCase()))
      const ingredientNames = new Set(
        existingIngs.map((i) => i.name.toLowerCase())
      )

      const conflicts = []

      ;(parsedData.recipes || []).forEach((r) => {
        if (recipeTitles.has(r.title.toLowerCase()))
          conflicts.push({ type: 'recipe', title: r.title })
        ;(r.ingredients || []).forEach((ing) => {
          if (ingredientNames.has(ing.name.toLowerCase()))
            conflicts.push({ type: 'ingredient', title: ing.name })
        })
      })

      if (conflicts.length) {
        setExistingRecipes(existingRecs)
        setExistingIngredients(existingIngs)
        setMergeConflicts(conflicts)
        return
      }

      await dataApi.importDatabase(parsedData, 'merge')
      alert('Import successful')
    } catch (err) {
      console.error('Failed to import database', err)
      alert(`Failed to import database: ${err.message}`)
  } finally {
      clearFile()
    }
  }

  const confirmMerge = async (selections) => {
    try {
      const payload = JSON.parse(JSON.stringify(parsedData || {}))
      for (const sel of selections) {
        const title = sel.title.toLowerCase()
        if (sel.type === 'recipe') {
          if (sel.action === 'keep-old') {
            payload.recipes = (payload.recipes || []).filter(
              (r) => r.title.toLowerCase() !== title
            )
          } else if (sel.action === 'use-new') {
            const existing = existingRecipes.find(
              (r) => r.title.toLowerCase() === title
            )
            if (existing) await recipesApi.delete(existing.id)
          }
        } else if (sel.type === 'ingredient') {
          if (sel.action === 'keep-old') {
            payload.recipes = (payload.recipes || []).map((r) => ({
              ...r,
              ingredients: (r.ingredients || []).filter(
                (ing) => ing.name.toLowerCase() !== title
              ),
            }))
          } else if (sel.action === 'use-new') {
            const existing = existingIngredients.find(
              (i) => i.name.toLowerCase() === title
            )
            if (existing) await ingredientsApi.remove(existing.id, true)
          }
        }
      }

      await dataApi.importDatabase(payload, 'merge')
      alert('Import successful')
    } catch (err) {
      console.error('Failed to import database', err)
      alert(`Failed to import database: ${err.message}`)
    } finally {
      clearFile()
      setMergeConflicts(null)
    }
  }

  const confirmOverwrite = async () => {
    try {
      await dataApi.importDatabase(parsedData, 'overwrite')
      alert('Import successful')
    } catch (err) {
      console.error('Failed to import database', err)
      alert(`Failed to import database: ${err.message}`)
    } finally {
      clearFile()
      setShowOverwriteModal(false)
    }
  }

  return (
    <>
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
        <Input type="file" onChange={handleFileChange} ref={fileInputRef} />
        <select
          className="rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
          style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
          value={mode}
          onChange={(e) => setMode(e.target.value)}
        >
          <option value="merge">Merge</option>
          <option value="overwrite">Overwrite</option>
        </select>
        {parsedData && <Button onClick={handleImport}>Import</Button>}
      </Card>
      </div>
      {showOverwriteModal && (
        <OverwriteConfirmModal
          onCancel={() => setShowOverwriteModal(false)}
          onConfirm={confirmOverwrite}
        />
      )}
      {mergeConflicts && (
        <MergeConflictModal
          conflicts={mergeConflicts}
          onCancel={() => setMergeConflicts(null)}
          onConfirm={confirmMerge}
        />
      )}
    </>
  )
}

