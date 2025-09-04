export function NavItem({ active, Icon, label, onClick, className='', ...props }) {
  const IconComponent = Icon
  return (
    <button
      onClick={onClick}
      className={`w-full text-left flex items-center gap-3 rounded-xl px-3 py-2 hover:opacity-95 ${active ? 'text-white' : 'text-[color:var(--text-strong)]'} ${className}`}
      style={{ backgroundColor: active ? 'var(--c-a1)' : 'transparent' }}
      type="button"
      {...props}
    >
      {IconComponent && <IconComponent className="h-5 w-5" />}
      <span className="text-sm font-medium">{label}</span>
    </button>
  )
}
