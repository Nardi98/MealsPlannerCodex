import React, { useState } from 'react';
import { test, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import RecipesPage from '../RecipesPage';
import { AppContext } from '../../App';

function renderWithContext(recipesData) {
  function Wrapper({ children }) {
    const [recipes, setRecipes] = useState(recipesData);
    const value = { recipes, setRecipes, plan: {}, setPlan: () => {} };
    return (
      <AppContext.Provider value={value}>
        <MemoryRouter>{children}</MemoryRouter>
      </AppContext.Provider>
    );
  }
  return render(
    <Wrapper>
      <RecipesPage />
    </Wrapper>
  );
}

test('displays course and score', () => {
  const data = [
    {
      id: 1,
      title: 'Soup',
      course: 'main',
      score: 4.5,
      tags: [],
      ingredients: [],
      procedure: '',
    },
  ];
  renderWithContext(data);
  expect(screen.getByText('Soup')).toBeInTheDocument();
  expect(screen.getByText('[main]')).toBeInTheDocument();
  expect(screen.getByText(/Score 4.50/)).toBeInTheDocument();
});

