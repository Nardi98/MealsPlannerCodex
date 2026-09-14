/**
 * Save `data` as a pretty-printed JSON file named `filename`, through a Blob
 * URL and a temporary link. The link and the URL are cleaned up even if the
 * click throws.
 */
export function downloadJson(data, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  try {
    link.click()
  } finally {
    link.remove()
    URL.revokeObjectURL(url)
  }
}
