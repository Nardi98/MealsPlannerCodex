import React from 'react'

export function Card({ variant = 'default', size = 'md', children, className = '', ...props }) {
  const paddingMap = { sm: 'p-2', md: 'p-4', lg: 'p-6' }[size]
  const base = 'rounded-2xl'
  const variants = {
    default: `border bg-white shadow-sm ${paddingMap}`,
    ghost: `${paddingMap}`,
  }
  const classes = `${base} ${variants[variant] || variants.default} ${className}`
  const style = variant === 'ghost' ? {} : { borderColor: 'var(--border)' }

  return (
    <div className={classes} style={style} {...props}>
      {children}
    </div>
  )
}
