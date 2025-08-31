import React, { useState } from 'react';
import Card from '../components/Card';
import Badge from '../components/Badge';
import Button from '../components/Button';
import Input from '../components/Input';
import Modal from '../components/Modal';

const initialRecipes = [
  {
    id: 1,
    title: 'Lemon Herb Chicken',
    course: 'main',
    score: 4.5,
    time: '40 min',
    kcal: 610,
    tags: ['hot', 'protein', 'quick'],
    ingredients: ['Chicken breasts', 'Lemon', 'Mixed herbs'],
    procedure: 'Marinate chicken with herbs and lemon then bake until cooked through.',
  },
  {
    id: 2,
    title: 'Mushroom Risotto',
    course: 'main',
    score: 4.2,
    time: '40 min',
    kcal: 620,
    tags: ['vegetarian'],
    ingredients: ['Rice', 'Mushrooms', 'Parmesan'],
    procedure: 'Cook rice slowly adding stock and mushrooms until creamy.',
  },
];

export default function Recipes() {
  const [recipes, setRecipes] = useState(initialRecipes);
  const [expanded, setExpanded] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ title: '', course: 'main', score: '', tags: '', ingredients: '', procedure: '' });
  const [search, setSearch] = useState('');

  const openNew = () => {
    setForm({ title: '', course: 'main', score: '', tags: '', ingredients: '', procedure: '' });
    setEditingId(null);
    setShowModal(true);
  };

  const openEdit = (recipe) => {
    setForm({
      title: recipe.title,
      course: recipe.course,
      score: recipe.score,
      tags: recipe.tags.join(', '),
      ingredients: recipe.ingredients.join('\n'),
      procedure: recipe.procedure,
    });
    setEditingId(recipe.id);
    setShowModal(true);
  };

  const saveRecipe = (e) => {
    e.preventDefault();
    const newRecipe = {
      id: editingId || Date.now(),
      title: form.title,
      course: form.course,
      score: parseFloat(form.score) || 0,
      time: '',
      kcal: 0,
      tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean),
      ingredients: form.ingredients.split('\n').map((l) => l.trim()).filter(Boolean),
      procedure: form.procedure,
    };
    setRecipes((prev) => {
      const others = prev.filter((r) => r.id !== editingId);
      return [...others, newRecipe];
    });
    setShowModal(false);
  };

  const deleteRecipe = (id) => {
    setRecipes((prev) => prev.filter((r) => r.id !== id));
  };

  const filteredRecipes = recipes.filter((r) => r.title.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="container">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-lg font-semibold">Recipes</h1>
        <div className="flex gap-2 items-center">
          <Input
            placeholder="Search recipes..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Button onClick={openNew}>+ New recipe</Button>
        </div>
      </div>

      <div className="flex flex-col gap-3">
        {filteredRecipes.map((r) => (
          <Card key={r.id} className="cursor-pointer" onClick={() => setExpanded(expanded === r.id ? null : r.id)}>
            <div className="flex justify-between items-start">
              <div>
                <div className="font-medium">{r.title}</div>
                <div className="text-xs text-[color:var(--text-muted)]">Score: {r.score}</div>
              </div>
              <span className="text-sm text-[color:var(--text-subtle)]">{r.course}</span>
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {r.tags.map((tag) => (
                <Badge key={tag}>{tag}</Badge>
              ))}
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
                  <Button
                    size="sm"
                    variant="a2"
                    onClick={(e) => {
                      e.stopPropagation();
                      openEdit(r);
                    }}
                  >
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteRecipe(r.id);
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            )}
          </Card>
        ))}
      </div>

      {showModal && (
        <Modal title={editingId ? 'Edit recipe' : 'New recipe'} onClose={() => setShowModal(false)}>
          <form onSubmit={saveRecipe} className="flex flex-col gap-3">
            <div>
              <label className="block text-sm mb-1">Title</label>
              <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
            </div>
            <div>
              <label className="block text-sm mb-1">Course</label>
              <select
                className="w-full border rounded-2xl px-2 py-1"
                style={{ borderColor: 'var(--border)' }}
                value={form.course}
                onChange={(e) => setForm({ ...form, course: e.target.value })}
              >
                <option value="main">main</option>
                <option value="side">side</option>
                <option value="dessert">dessert</option>
              </select>
            </div>
            <div>
              <label className="block text-sm mb-1">Score</label>
              <Input
                type="number"
                step="0.1"
                value={form.score}
                onChange={(e) => setForm({ ...form, score: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm mb-1">Tags (comma separated)</label>
              <Input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm mb-1">Ingredients (one per line)</label>
              <textarea
                className="w-full border rounded-2xl px-2 py-1"
                style={{ borderColor: 'var(--border)' }}
                rows={3}
                value={form.ingredients}
                onChange={(e) => setForm({ ...form, ingredients: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm mb-1">Procedure</label>
              <textarea
                className="w-full border rounded-2xl px-2 py-1"
                style={{ borderColor: 'var(--border)' }}
                rows={3}
                value={form.procedure}
                onChange={(e) => setForm({ ...form, procedure: e.target.value })}
              />
            </div>
            <div className="flex justify-end gap-2 mt-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => setShowModal(false)}>
                Cancel
              </Button>
              <Button type="submit" size="sm">
                Save
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
