/**
 * An icon-only control at the 44px tap target design guide §8.4 requires.
 *
 * Before this existed, `inline-flex h-11 w-11 items-center justify-center` was
 * retyped at every icon action, and each site independently remembered
 * `type="button"`, the accessible name, and the title — so the icons that
 * predated the rule were 16px and unlabelled. The name is required rather than
 * optional: an icon button without one is unreachable, and that was the bug.
 */
export function IconButton({
  Icon,
  label,
  onClick,
  stopPropagation = false,
  color,
  className = '',
  ...props
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={`inline-flex h-11 w-11 shrink-0 items-center justify-center ${className}`}
      style={{ color }}
      onClick={(event) => {
        // Icon actions inside a clickable cell must not also select the cell.
        if (stopPropagation) event.stopPropagation()
        onClick?.(event)
      }}
      {...props}
    >
      {Icon && <Icon className="h-5 w-5" />}
    </button>
  )
}
