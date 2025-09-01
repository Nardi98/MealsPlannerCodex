import React from 'react';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import RecipeForm from '../RecipeForm';

afterEach(() => {
  cleanup();
});

test('course selector defaults to main', () => {
  render(<RecipeForm />);
  const select = screen.getByLabelText(/course/i);
  expect(select.value).toBe('main');
});

test('submitting recipe calls onSave with form data', () => {
  const onSave = vi.fn();
  render(<RecipeForm onSave={onSave} />);
  fireEvent.change(screen.getByLabelText(/title/i), { target: { value: 'Pie' } });
  fireEvent.change(screen.getByLabelText(/servings/i), { target: { value: '4' } });
  fireEvent.change(screen.getByLabelText(/course/i), { target: { value: 'dessert' } });
  fireEvent.click(screen.getByText('Add ingredient'));
  fireEvent.change(screen.getByPlaceholderText('Ingredient 1'), { target: { value: 'Flour' } });
  fireEvent.change(screen.getByLabelText(/tags/i), { target: { value: 'sweet, baked' } });
  fireEvent.change(screen.getByLabelText(/procedure/i), { target: { value: 'Mix and bake' } });
  fireEvent.click(screen.getByLabelText(/bulk prep/i));
  fireEvent.click(screen.getByText('Save'));
  expect(onSave).toHaveBeenCalledWith({
    title: 'Pie',
    course: 'dessert',
    ingredients: ['Flour'],
    tags: ['sweet', 'baked'],
    procedure: 'Mix and bake',
    servings: 4,
    bulkPrep: true,
  });
});
