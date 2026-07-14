import { describe, it, expect } from 'vitest'
import { dishIcon, courseColor, COURSE_ICONS } from '../recipeIcons'

describe('dishIcon', () => {
  it('uses the course icon when no keyword matches', () => {
    expect(dishIcon({ title: 'Roasted Chicken', course: 'main' })).toBe(
      COURSE_ICONS.main
    )
  })

  it('lets a title keyword override the course icon', () => {
    expect(dishIcon({ title: 'Creamy Pasta Bake', course: 'main' })).toBe(
      'noodles'
    )
  })

  it('falls back to the default glyph for an unknown course', () => {
    expect(dishIcon({ title: 'Something', course: 'brunch' })).toBe(
      'silverware-fork-knife'
    )
  })
})

describe('courseColor', () => {
  it('maps each known course to a category color variable', () => {
    expect(courseColor.main).toBe('var(--cat-terracotta)')
    expect(courseColor.side).toBe('var(--cat-olive)')
    expect(courseColor['first-course']).toBe('var(--cat-sky)')
    expect(courseColor.dessert).toBe('var(--cat-berry)')
  })
})
