import React from 'react';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';
import Recipes from '../Recipes';

afterEach(() => cleanup());

describe('Recipes page', () => {
  it('displays course and score for a recipe', () => {
    render(<Recipes />);
    expect(screen.getByText('Lemon Herb Chicken')).toBeInTheDocument();
    expect(screen.getAllByText('main').length).toBeGreaterThan(0);
    expect(screen.getByText(/Score: 4.5/)).toBeInTheDocument();
  });

  it('opens modal to add a recipe', () => {
    render(<Recipes />);
    fireEvent.click(screen.getByText('+ New recipe'));
    expect(screen.getByText('New recipe')).toBeInTheDocument();
  });
});
