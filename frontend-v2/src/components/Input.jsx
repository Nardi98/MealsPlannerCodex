// `text-base` is not cosmetic: iOS Safari auto-zooms a focused input whose
// font is under 16px and never zooms back out. Design guide §8.4 supplies the
// 44px minimum height.
//
// `as` lets a native control that is not an <input> — a <select>, say — wear
// the same border, radius and height instead of copying the token set.
export function Input({ as='input', className='', style={}, children, ...props }) {
  // Bound to a capitalised local so JSX renders the tag rather than a literal
  // <as> element.
  const Control = as
  return (
    <Control {...props}
      className={`border min-h-11 px-3 py-2 text-base ${className}`}
      style={{
        borderRadius: 'var(--radius-md)',
        borderColor: 'var(--border-default)',
        color: 'var(--text-strong)',
        fontFamily: 'var(--font-body)',
        ...style,
      }}>{children}</Control>
  )
}
