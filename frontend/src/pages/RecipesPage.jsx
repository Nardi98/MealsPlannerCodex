import React, { useContext, useState } from 'react';
import { BookmarkIcon, TagIcon } from '@heroicons/react/24/outline';
import { motion } from 'framer-motion';
import { AppContext } from '../App';
import { Card } from '../components/Card';
import { Input } from '../components/Input';
import { Button } from '../components/Button';
import { Badge } from '../components/Badge';
import RecipeForm from '../components/RecipeForm';

export default function RecipesPage() {
  const { recipes, setRecipes } = useContext(AppContext);
  const [expanded, setExpanded] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const toggle = (id) => setExpanded(expanded === id ? null : id);

  const handleSave = (recipe) => {
    const newRecipe = {
      id: Date.now(),
      score: 0,
      tags: [],
      ...recipe,
    };
    setRecipes([...recipes, newRecipe]);
    setShowModal(false);
  };

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-[color:var(--text-subtle)]">
          <BookmarkIcon className="h-5 w-5" /> Recipes
        </div>
        <div className="flex items-center gap-2">
          <Input placeholder="Search recipes…" className="w-56" />
          <Button variant="a1" onClick={() => setShowModal(true)}>
            + New recipe
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3">
        {recipes.map((r) => (
          <motion.div key={r.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
            <div
              className="rounded-2xl border p-3 bg-white cursor-pointer"
              style={{ borderColor: 'var(--border)' }}
              onClick={() => toggle(r.id)}
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-medium">
                    {r.title}{' '}
                    <span className="text-xs font-normal text-[color:var(--text-subtle)]">[{r.course}]</span>
                  </div>
                  <div className="mt-0.5 text-xs text-[color:var(--text-subtle)]">
                    Score {Number(r.score ?? 0).toFixed(2)}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {r.tags.map((t) => (
                    <Badge key={t} tone="a3" className="flex items-center gap-1">
                      <TagIcon className="h-3 w-3" />{t}
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
                    <Button size="sm" variant="a2" onClick={(e) => e.stopPropagation()}>
                      Edit
                    </Button>
                    <Button size="sm" variant="danger" onClick={(e) => e.stopPropagation()}>
                      Delete
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        ))}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4">
          <Card className="w-full max-w-lg">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-medium">New Recipe</h2>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                aria-label="Close"
                className="text-sm"
              >
                ✕
              </button>
            </div>
            <RecipeForm onSave={handleSave} onCancel={() => setShowModal(false)} />
          </Card>
        </div>
      )}
    </Card>
  );
}

