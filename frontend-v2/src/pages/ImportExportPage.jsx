import React from 'react'
import {
  Card,
  Button,
  Input,
  OverwriteConfirmModal,
  MergeConflictModal,
  ImportRecipeModal,
} from '../components'
import { dataApi } from '../api/dataApi'
import { recipesApi } from '../api/recipesApi'

const COUNT_LABELS = [
  ['recipes', 'recipe'],
  ['ingredients', 'ingredient'],
  ['tags', 'tag'],
  ['meal_plans', 'meal plan'],
]

/** What actually landed, so an import of nothing can never read as a success. */
function importSummary(result) {
  const counts = result?.imported ?? {}
  const parts = COUNT_LABELS.filter(([key]) => counts[key]).map(
    ([key, noun]) => `${counts[key]} ${noun}${counts[key] === 1 ? '' : 's'}`
  )
  return parts.length ? `Imported ${parts.join(', ')}.` : 'Imported nothing.'
}

export default function ImportExportPage() {
  const [file, setFile] = React.useState(null)
  const [parsedData, setParsedData] = React.useState(null)
  const [mode, setMode] = React.useState('merge')
  const [showOverwriteModal, setShowOverwriteModal] = React.useState(false)
  // The conflict modal's whole input: the clashing titles, the payload to
  // send once they are resolved, and the recipes a "use new" has to replace.
  const [pending, setPending] = React.useState(null)
  const [showImportRecipe, setShowImportRecipe] = React.useState(false)
  const [importedTitle, setImportedTitle] = React.useState('')
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
      const existing = await recipesApi.fetchAll()
      const existingTitles = new Set(existing.map((r) => r.title.toLowerCase()))

      // Only titles can conflict. Ingredients are a shared pantry and the
      // backend already reuses an existing one by name instead of duplicating
      // it, so an overlapping ingredient name is the normal case, not a
      // question to put to the user.
      const conflicts = (parsedData.recipes || [])
        .filter((r) => existingTitles.has(r.title.toLowerCase()))
        .map((r) => ({ title: r.title }))

      if (conflicts.length) {
        // The payload and the recipes it clashes with travel *with* the
        // conflicts rather than being read back out of state later, so
        // clearing the file below cannot leave confirmMerge with nothing to
        // send. That is exactly how this page used to import an empty object
        // and report it as a success.
        setPending({ conflicts, payload: parsedData, existing })
        return
      }

      const result = await dataApi.importDatabase(parsedData, 'merge')
      alert(importSummary(result))
    } catch (err) {
      console.error('Failed to import database', err)
      alert(`Failed to import database: ${err.message}`)
    } finally {
      clearFile()
    }
  }

  const confirmMerge = async (selections) => {
    try {
      const payload = JSON.parse(JSON.stringify(pending.payload))
      for (const sel of selections) {
        const title = sel.title.toLowerCase()
        if (sel.action === 'keep-old') {
          payload.recipes = (payload.recipes || []).filter(
            (r) => r.title.toLowerCase() !== title
          )
        } else if (sel.action === 'use-new') {
          const old = pending.existing.find(
            (r) => r.title.toLowerCase() === title
          )
          if (old) await recipesApi.delete(old.id)
        }
      }

      const result = await dataApi.importDatabase(payload, 'merge')
      alert(importSummary(result))
    } catch (err) {
      console.error('Failed to import database', err)
      alert(`Failed to import database: ${err.message}`)
    } finally {
      clearFile()
      setPending(null)
    }
  }

  const confirmOverwrite = async () => {
    try {
      const result = await dataApi.importDatabase(parsedData, 'overwrite')
      alert(importSummary(result))
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
          className="rounded-xl border px-3 py-2 text-sm"
          style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
          value={mode}
          onChange={(e) => setMode(e.target.value)}
        >
          <option value="merge">Merge</option>
          <option value="overwrite">Overwrite</option>
        </select>
        {parsedData && <Button onClick={handleImport}>Import</Button>}
      </Card>

      <Card className="space-y-3">
        <div>
          <h2 className="text-lg font-medium" style={{ color: 'var(--text-strong)' }}>
            Import a recipe from the web
          </h2>
          <p className="text-sm text-[color:var(--text-subtle)]">
            Turn a recipe from another website into an importable one with the help
            of a chatbot.
          </p>
        </div>
        {importedTitle && (
          <p className="text-sm" style={{ color: 'var(--c-pos)' }}>
            Added “{importedTitle}”.
          </p>
        )}
        <Button onClick={() => setShowImportRecipe(true)}>Import a recipe</Button>
      </Card>
      </div>
      {showOverwriteModal && (
        <OverwriteConfirmModal
          onCancel={() => setShowOverwriteModal(false)}
          onConfirm={confirmOverwrite}
        />
      )}
      {pending && (
        <MergeConflictModal
          conflicts={pending.conflicts}
          onCancel={() => setPending(null)}
          onConfirm={confirmMerge}
        />
      )}
      {showImportRecipe && (
        <ImportRecipeModal
          onClose={() => setShowImportRecipe(false)}
          onCreated={(created) => {
            setImportedTitle(created?.title || '')
            setShowImportRecipe(false)
          }}
        />
      )}
    </>
  )
}

