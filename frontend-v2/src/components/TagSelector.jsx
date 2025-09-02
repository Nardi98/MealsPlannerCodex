export default function TagSelector({ label, tags = [], selected = [], onChange }) {
  const handleChange = (e) => {
    const options = Array.from(e.target.selectedOptions).map((o) => o.value)
    onChange(options)
  }

  return (
    <label className="flex flex-col text-sm col-span-2">
      {label && <span className="mb-1">{label}</span>}
      <select
        multiple
        value={selected}
        onChange={handleChange}
        className="border rounded p-2"
        style={{ borderColor: 'var(--border)' }}
      >
        {tags.map((tag) => (
          <option key={tag} value={tag}>
            {tag}
          </option>
        ))}
      </select>
    </label>
  )
}
