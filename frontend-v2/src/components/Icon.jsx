import React from 'react'

// Icon renders a single glyph inline as raw SVG (fetched + inlined so `color`
// is picked up naturally, like @heroicons/react's own components).
//
//  - set="heroicons" (default) — 24px grid, outline or solid, from the
//    heroicons npm package via CDN.
//  - set="mdi" — Material Design Icons via the Iconify CDN, used for food /
//    dish glyphs that Heroicons doesn't provide.

const cache = {}
let styleInjected = false

function ensureIconStyle() {
  if (styleInjected || typeof document === 'undefined') return
  styleInjected = true
  const tag = document.createElement('style')
  tag.textContent = [
    '[data-mp-icon] svg { width: 100%; height: 100%; display: block; }',
    '[data-mp-icon-set="mdi"] svg, [data-mp-icon-set="mdi"] svg * { fill: currentColor; }',
  ].join('\n')
  document.head.appendChild(tag)
}

export function Icon({
  name,
  set = 'heroicons',
  variant = 'outline',
  size = 20,
  color = 'currentColor',
  className = '',
  style = {},
}) {
  const url =
    set === 'heroicons'
      ? `https://cdn.jsdelivr.net/npm/heroicons@2.1.5/24/${variant}/${name}.svg`
      : `https://api.iconify.design/${set}/${name}.svg`
  const [svg, setSvg] = React.useState(
    typeof cache[url] === 'string' ? cache[url] : null
  )

  React.useEffect(() => {
    ensureIconStyle()
  }, [])

  React.useEffect(() => {
    let cancelled = false
    // Cache the in-flight promise (not just the resolved text) so that the many
    // Icons sharing a URL on first paint issue a single fetch and all await it.
    if (!cache[url]) {
      cache[url] = fetch(url)
        .then((res) => (res.ok ? res.text() : Promise.reject(res.status)))
        .then((text) => {
          cache[url] = text
          return text
        })
        .catch(() => {
          delete cache[url]
          return null
        })
    }
    Promise.resolve(cache[url]).then((text) => {
      if (!cancelled && text) setSvg(text)
    })
    return () => {
      cancelled = true
    }
  }, [url])

  return (
    <span
      role="img"
      aria-label={name}
      data-mp-icon=""
      data-mp-icon-set={set}
      className={className}
      style={{
        display: 'inline-flex',
        flexShrink: 0,
        width: size,
        height: size,
        color,
        lineHeight: 0,
        ...style,
      }}
      dangerouslySetInnerHTML={svg ? { __html: svg } : undefined}
    />
  )
}
