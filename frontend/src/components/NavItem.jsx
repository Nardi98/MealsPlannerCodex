export function NavItem({ active, Icon, label, onClick }) {
  return (
    <button
      onClick={onClick}
      type="button"
      className={`w-full text-left flex items-center gap-3 rounded-xl px-3 py-2 hover:opacity-95 ${
        active ? 'text-white' : 'text-[color:var(--text-strong)]'
      }`}
      style={{ backgroundColor: active ? 'var(--c-a1)' : 'transparent' }}
    >
      <Icon className="h-5 w-5" />
      <span className="text-sm font-medium">{label}</span>
    </button>
  );
}
