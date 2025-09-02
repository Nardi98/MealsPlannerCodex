export default function TagSelector({ label, tags = [], selected = [], onChange }) {
  const toggle = (tag) => {
    if (selected.includes(tag)) {
      onChange(selected.filter((t) => t !== tag))
    } else {
      onChange([...selected, tag])
    }
  }

  return (
    <div className="flex flex-col text-sm col-span-2">
      {label && <span className="mb-1">{label}</span>}
      <div className="flex flex-wrap gap-2">
        {tags.map((tag) => (
          <label key={tag} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={selected.includes(tag)}
              onChange={() => toggle(tag)}
              className="h-4 w-4 rounded border"
              style={{ borderColor: 'var(--border)' }}
            />
            <span style={{ color: 'var(--text-strong)' }}>{tag}</span>
          </label>
        ))}
      </div>
    </div>
  )
}
