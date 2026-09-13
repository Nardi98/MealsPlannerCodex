import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from 'vitest'

// RM-8: the client-side starter pack is gone for good -- the recipe library
// (POST /catalog/adopt) is the only way to add catalog recipes (RM-9). A
// dangling import would fail the suite on its own; this also catches comments,
// storage keys and copies of the module under another path.
//
// The needles are concatenated so this file does not match itself.
const NEEDLES = ['starter' + 'Recipes', 'StarterRecipes' + 'Modal']

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    return entry.isDirectory() ? walk(full) : [full]
  })
}

test('no file under src references the removed starter pack', () => {
  const offenders = walk(SRC).flatMap((file) => {
    const text = fs.readFileSync(file, 'utf-8')
    return NEEDLES.filter((needle) => text.includes(needle)).map(
      (needle) => `${path.relative(SRC, file)}: ${needle}`,
    )
  })

  expect(offenders).toEqual([])
})
