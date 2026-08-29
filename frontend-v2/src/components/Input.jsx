// `text-base` is not cosmetic: iOS Safari auto-zooms a focused input whose
// font is under 16px and never zooms back out. Design guide §8.4 supplies the
// 44px minimum height.
export function Input({ className='', style={}, ...props }) {
  return (
    <input {...props}
      className={`border min-h-11 px-3 py-2 text-base ${className}`}
      style={{
        borderRadius: 'var(--radius-md)',
        borderColor: 'var(--border-default)',
        color: 'var(--text-strong)',
        fontFamily: 'var(--font-body)',
        ...style,
      }}/>
  )
}
