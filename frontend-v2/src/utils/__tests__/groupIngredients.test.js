import { describe, it, expect } from 'vitest'
import { groupByCategory } from '../groupIngredients'
import { UNCATEGORIZED } from '../../constants/categories'

const byCategory = (groups) =>
  Object.fromEntries(groups.map((g) => [g.category, g.items.map((i) => i.name)]))

describe('groupByCategory', () => {
  it('places a multi-category ingredient in every group', () => {
    const groups = groupByCategory([
      { id: 1, name: 'Lentils', categories: ['Legumes', 'Protein'] },
    ])
    const map = byCategory(groups)
    expect(map['Legumes']).toEqual(['Lentils'])
    expect(map['Protein']).toEqual(['Lentils'])
  })

  it('places uncategorized ingredients under UNCATEGORIZED only', () => {
    const groups = groupByCategory([
      { id: 2, name: 'Mystery', categories: [] },
      { id: 3, name: 'NoField' },
    ])
    const map = byCategory(groups)
    expect(map[UNCATEGORIZED]).toEqual(['Mystery', 'NoField'])
  })

  it('orders groups by canonical order with UNCATEGORIZED last', () => {
    const groups = groupByCategory([])
    expect(groups[0].category).toBe('Vegetables')
    expect(groups[groups.length - 1].category).toBe(UNCATEGORIZED)
  })
})
