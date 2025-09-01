import React, { useContext, useEffect, useState } from 'react';
import { BookmarkIcon, TagIcon } from '@heroicons/react/24/outline';
import { motion } from 'framer-motion';
import { AppContext } from '../App';
import { Card } from '../components/Card';
import { Input } from '../components/Input';
import { Button } from '../components/Button';
import { Badge } from '../components/Badge';
import RecipeForm from '../components/RecipeForm';
import { recipesApi } from '../api';

export default function RecipesPage() {
  const { recipes, setRecipes } = useContext(AppContext);
  const [expanded, setExpanded] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [loading, setLoading] = useState(!recipes.length);
  const [error, setError] = useState(null);
  const toggle = (id) => setExpanded(expanded === id ? null : id);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await recipesApi.fetchAll();
      const normalised = data.map((r) => {
        const { ingredients = [], tags = [], servings_default, bulk_prep, ...rest } = r;
        return {
          ...rest,
          ingredients: ingredients.map((ing) => ing.name ?? ing),
          tags: tags.map((t) => (typeof t === 'string' ? t : t.name)),
          servings: servings_default ?? null,
          bulkPrep: bulk_prep ?? false,
        };
      });
      setRecipes(normalised);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!recipes.length) {
      refresh();
    } else {
      setLoading(false);
    }
  }, []);

  const handleSave = async (recipe) => {
    const payload = {
      title: recipe.title,
      course: recipe.course,
      ingredients: recipe.ingredients.map((i) => ({ name: i })),
      tags: recipe.tags,
      procedure: recipe.procedure,
      servings_default: recipe.servings,
      bulk_prep: recipe.bulkPrep,
    };
    try {
      if (editing) {
        await recipesApi.update(editing.id, payload);
      } else {
        await recipesApi.create(payload);
      }
      setShowModal(false);
      setEditing(null);
      refresh();
    } catch (err) {
      setError(err.message);
    }
  };

  const startNew = () => {
    setEditing(null);
    setShowModal(true);
  };

  const handleEdit = (recipe, e) => {
    e.stopPropagation();
    setEditing({
      ...recipe,
      ingredients: [...recipe.ingredients],
      tags: [...recipe.tags],
    });
    setShowModal(true);
  };

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    try {
      await recipesApi.delete(id);
      refresh();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-[color:var(--text-subtle)]">
          <BookmarkIcon className="h-5 w-5" /> Recipes
        </div>
          <div className="flex items-center gap-2">
            <Input placeholder="Search recipes…" className="w-56" />
            <Button variant="a1" onClick={startNew}>
              + New recipe
            </Button>
          </div>
        </div>
        {loading ? (
          <p>Loading…</p>
        ) : error ? (
          <p className="text-red-600">Error: {error}</p>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {recipes.map((r) => (
              <motion.div
                key={r.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
              >
                <div
                  className="rounded-2xl border p-3 bg-white cursor-pointer"
                  style={{ borderColor: 'var(--border)' }}
                  onClick={() => toggle(r.id)}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="font-medium">
                        {r.title}{' '}
                        <span className="text-xs font-normal text-[color:var(--text-subtle)]">
                          [{r.course}] {Number(r.score ?? 0).toFixed(2)}
                        </span>
                      </div>
                      {(r.time || r.kcal) && (
                        <div className="mt-0.5 text-xs text-[color:var(--text-subtle)]">
                          {r.time}
                          {r.time && r.kcal ? ' • ' : ''}
                          {r.kcal ? `${r.kcal} kcal` : ''}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      {r.hot && <Badge tone="a2">hot</Badge>}
                      {r.tags.map((t) => (
                        <Badge key={t} tone="a3" className="flex items-center gap-1">
                          <TagIcon className="h-3 w-3" />
                          {t}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {expanded === r.id && (
                    <div className="mt-3">
                      <div className="text-sm font-medium mb-1">Ingredients</div>
                      <ul className="list-disc list-inside text-sm mb-2">
                        {r.ingredients.map((ing, i) => (
                          <li key={i}>{ing}</li>
                        ))}
                      </ul>
                      <div className="text-sm font-medium mb-1">Procedure</div>
                      <p className="text-sm mb-3">{r.procedure}</p>
                      <div className="flex justify-end gap-2">
                        <Button size="sm" variant="a2" onClick={(e) => handleEdit(r, e)}>
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={(e) => handleDelete(r.id, e)}
                        >
                          Delete
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {showModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4">
            <Card className="w-full max-w-lg">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-medium">
                  {editing ? 'Edit Recipe' : 'New Recipe'}
                </h2>
                <button
                  type="button"
                  onClick={() => {
                    setShowModal(false);
                    setEditing(null);
                  }}
                  aria-label="Close"
                  className="text-sm"
                >
                  ✕
                </button>
              </div>
              <RecipeForm
                initial={editing || undefined}
                onSave={handleSave}
                onCancel={() => {
                  setShowModal(false);
                  setEditing(null);
                }}
              />
            </Card>
          </div>
        )}
      </Card>
    );
  }

