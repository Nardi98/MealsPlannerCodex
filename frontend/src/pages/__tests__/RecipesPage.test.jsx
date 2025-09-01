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
      tags: ['quick'],
      ingredients: [],
      procedure: '',
      hot: true,
      time: '10m',
      kcal: 200,
    },
  ];
  renderWithContext(data);
  expect(screen.getByText('Soup')).toBeInTheDocument();
  expect(screen.getByText('[main] 4.50')).toBeInTheDocument();
  expect(screen.getByText('10m • 200 kcal')).toBeInTheDocument();
  expect(screen.getByText('hot')).toBeInTheDocument();
  expect(screen.getByText('quick')).toBeInTheDocument();
});

