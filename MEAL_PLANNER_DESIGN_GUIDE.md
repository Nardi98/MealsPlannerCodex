
# Meal Planner — Frontend Design Guide
**Scope:** This guide specifies the *Recipes* page and site‑wide conventions so another AI (or dev) can reproduce the UI exactly as in our current demo.  
**Out of scope (titles only):** Week Planner, Shopping List, Import/Export Database.

> Stack: React + Tailwind (utility classes), framer-motion, @heroicons/react/24/outline.  
> Style tokens are exposed as CSS variables (see below).

---

## 0) Repo & File Layout (frontend)
```
/src/
  components/
    Button.jsx
    Badge.jsx
    Card.jsx
    Input.jsx
    NavItem.jsx
  pages/
    RecipesPage.jsx        # this page (full spec below)
    WeekPlannerPage.jsx    # (title only – empty)
    ShoppingListPage.jsx   # (title only – empty)
    ImportExportPage.jsx   # (title only – empty)
  App.jsx                  # shell header + sidebar + router-ish state
  tokens.js                # token defaults (optional)
```

You may keep everything in a single file for the demo (as we did), but when turning this into a project, split into the structure above.

---

## 1) Design Tokens (CSS variables)
Set these on a top-level container (or `:root`). They control color and borders across components.

```css
/* Required CSS variables */
:root {
  --c-white: #F8FAF9;
  --c-pos:   #0C3A2D;
  --c-neg:   #BD210F;
  --c-a1:    #6D9773;
  --c-a2:    #FFB902;
  --c-a3:    #BB8A52;
  --border:        #e2e8f0;
  --text-strong:   #0C3A2D;
  --text-muted:    #475569;
  --text-subtle:   #64748b;
}
```

If the host does not inject tokens, use these defaults in JS and spread them as inline `style` onto the root container.

```jsx
// tokens.js (optional)
export const DEFAULT_TOKENS = {
  white: '#F8FAF9', pos: '#0C3A2D', neg: '#BD210F',
  a1: '#6D9773', a2: '#FFB902', a3: '#BB8A52',
  border: '#e2e8f0', textStrong: '#0C3A2D',
  textMuted: '#475569', textSubtle: '#64748b',
};
export function useCssVars(tokens = DEFAULT_TOKENS) {
  return {
    ['--c-white']: tokens.white, ['--c-pos']: tokens.pos, ['--c-neg']: tokens.neg,
    ['--c-a1']: tokens.a1, ['--c-a2']: tokens.a2, ['--c-a3']: tokens.a3,
    ['--border']: tokens.border, ['--text-strong']: tokens.textStrong,
    ['--text-muted']: tokens.textMuted, ['--text-subtle']: tokens.textSubtle,
  };
}
```

---

## 2) Site-Wide Layout
- **Header:** left logo + product name; right search input + ghost button; user avatar stub.
- **Sidebar:** vertical nav with rounded active item (filled `--c-a1`, white text). Items:
  - Week planner
  - Recipes (default active)
  - Shopping list
- **Content area:** Cards with soft borders and 2xl rounding. White backgrounds.

Minimal shell (copy/paste):

```jsx
import { SwatchIcon, CalendarDaysIcon, BookmarkIcon, ShoppingCartIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import React, { useState } from 'react';

function NavItem({ active, Icon, label, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left flex items-center gap-3 rounded-xl px-3 py-2 hover:opacity-95 ${active ? 'text-white' : 'text-[color:var(--text-strong)]'}`}
      style={{ backgroundColor: active ? 'var(--c-a1)' : 'transparent' }}
      type="button"
    >
      <Icon className="h-5 w-5" /><span className="text-sm font-medium">{label}</span>
    </button>
  );
}

export default function AppShell({ children }) {
  const [active, setActive] = useState('recipes');

  return (
    <div className="min-h-screen" style={{ background: 'var(--c-white)', color: 'var(--text-strong)' }}>
      <header className="border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <SwatchIcon className="h-6 w-6 text-[color:var(--c-a3)]" />
            <span className="font-semibold">Meal Planner</span>
            <span className="text-xs text-[color:var(--text-subtle)] ml-2">Demo UI — Updated Style</span>
          </div>
          <div className="hidden md:flex items-center gap-2">
            <input className="rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)] w-64"
                   placeholder="Search…" style={{ borderColor: 'var(--border)' }} />
            <button className="inline-flex items-center gap-2 rounded-2xl border px-3 py-2 text-sm hover:opacity-95"
                    style={{ color: 'var(--text-strong)' }}>Search</button>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-4 px-4 py-6 md:grid-cols-[16rem_1fr]">
        <aside className="space-y-2">
          <div className="rounded-2xl border bg-white p-4 shadow-sm" style={{ borderColor: 'var(--border)' }}>
            <div className="grid grid-cols-1 gap-1">
              <NavItem active={active==='planner'} onClick={()=>setActive('planner')} Icon={CalendarDaysIcon} label="Week planner" />
              <NavItem active={active==='recipes'} onClick={()=>setActive('recipes')} Icon={BookmarkIcon} label="Recipes" />
              <NavItem active={active==='list'}    onClick={()=>setActive('list')}    Icon={ShoppingCartIcon} label="Shopping list" />
            </div>
          </div>
        </aside>
        <section className="space-y-4">{children}</section>
      </main>
    </div>
  );
}
```

---

## 3) UI Primitives
Use these EXACT props/variants so downstream code can copy/paste and be consistent.

```jsx
// Button.jsx
export function Button({ variant='primary', size='md', Icon, children, className='', ...props }) {
  const map = {
    primary: { bg: 'var(--c-pos)', fg: '#fff' },
    danger:  { bg: 'var(--c-neg)', fg: '#fff' },
    a1:      { bg: 'var(--c-a1)', fg: '#fff' },
    a2:      { bg: 'var(--c-a2)', fg: '#121212' },
    ghost:   { bg: 'transparent', fg: 'var(--text-strong)', border: 'var(--border)' },
  }[variant];
  const sizeMap = { sm:'px-2 py-1 text-xs', md:'px-3 py-2 text-sm', lg:'px-4 py-2.5 text-sm' }[size];

  return (
    <button type="button"
      className={`inline-flex items-center gap-2 rounded-2xl shadow-sm hover:opacity-95 border ${sizeMap} ${className}`}
      style={{ backgroundColor: map?.bg, color: map?.fg, borderColor: map?.border || 'transparent' }}
      {...props}>
      {Icon && <Icon className="h-5 w-5" />}{children}
    </button>
  );
}
```

```jsx
// Badge.jsx
export function Badge({ tone='a3', children }) {
  const fg = `var(--c-${tone})`;
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
          style={{ backgroundColor: `color-mix(in srgb, ${fg} 14%, transparent)`, color: fg }}>
      {children}
    </span>
  );
}
```

```jsx
// Card.jsx
export function Card({ children, className='' }) {
  return (
    <div className={`rounded-2xl border bg-white p-4 shadow-sm ${className}`} style={{ borderColor: 'var(--border)' }}>
      {children}
    </div>
  );
}
```

```jsx
// Input.jsx
export function Input({ className='', ...props }) {
  return (
    <input {...props}
      className={`rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)] ${className}`}
      style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}/>
  );
}
```

---

## 4) Recipes Page — Exact Spec

### 4.1 Page Header
- Left: “Recipes” label with bookmark icon.
- Right: search input (`placeholder="Search recipes…"`, width `w-56`) and “New recipe” button (`variant="a1"`).

```jsx
import { BookmarkIcon, PlusIcon } from '@heroicons/react/24/outline';
import { Card } from '../components/Card';
import { Input } from '../components/Input';
import { Button } from '../components/Button';

export default function RecipesPage() {
  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-[color:var(--text-subtle)]">
          <BookmarkIcon className="h-5 w-5" /> Recipes
        </div>
        <div className="flex items-center gap-2">
          <Input placeholder="Search recipes…" className="w-56" />
          <Button variant="a1" Icon={PlusIcon}>New recipe</Button>
        </div>
      </div>
      {/* cards go here */}
    </Card>
  );
}
```

### 4.2 Card Layout (one per row)
- Grid is **always single column**: `grid grid-cols-1 gap-3`.
- Each card uses a soft border, rounded 2xl, white background.
- The **entire card is clickable** and toggles expansion.

### 4.3 Card Header (collapsed state)
- Title: bold.
- Meta line: `time • kcal`, `text-xs` and `--text-subtle` color.
- Right side: tags as `Badge tone="a3"`; if “hot”, also show `Badge tone="a2"` with label `hot`.

### 4.4 Expansion Behavior
- Click anywhere on the card toggles (single-open pattern: only one expanded at a time).
- Expanded content shows:
  - **Ingredients**: bulleted list (`ul.list-disc.list-inside`).
  - **Procedure**: paragraph text with comfortable line height.
  - **Actions (right aligned):** **Edit** (yellow, `variant="a2"`) and **Delete** (red, `variant="danger"`).

### 4.5 Reference Implementation (copy/paste)
This is the canonical implementation used in the demo. Use it as-is.

```jsx
import { BookmarkIcon, TagIcon, PlusIcon } from '@heroicons/react/24/outline';
import { motion } from 'framer-motion';
import { Card } from '../components/Card';
import { Input } from '../components/Input';
import { Button } from '../components/Button';
import { Badge } from '../components/Badge';

const demoRecipes = [
  { id: 1, title: "Lemon Herb Chicken", time: "25 min", kcal: 480, tags: ["protein", "quick"], hot: true, ingredients:["Chicken breast","Lemon","Olive oil"], procedure:"Mix marinade, coat chicken, grill 25 min." },
  { id: 2, title: "Mushroom Risotto", time: "40 min", kcal: 620, tags: ["vegetarian"], hot: false, ingredients:["Arborio rice","Mushrooms","Parmesan"], procedure:"Sauté mushrooms, cook rice with stock, finish with cheese." },
  { id: 3, title: "Pasta Primavera", time: "20 min", kcal: 520, tags: ["pasta", "spring"], hot: false, ingredients:["Pasta","Zucchini","Carrots"], procedure:"Boil pasta, sauté vegetables, toss together." },
  { id: 4, title: "Tofu Stir Fry", time: "18 min", kcal: 410, tags: ["vegan", "leftovers"], hot: true, ingredients:["Tofu","Soy sauce","Broccoli"], procedure:"Fry tofu, add vegetables, stir in sauce." },
];

export default function RecipesPage() {
  const [expanded, setExpanded] = React.useState(null);
  const toggle = (id) => setExpanded(expanded === id ? null : id);

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-[color:var(--text-subtle)]">
          <BookmarkIcon className="h-5 w-5" /> Recipes
        </div>
        <div className="flex items-center gap-2">
          <Input placeholder="Search recipes…" className="w-56" />
          <Button variant="a1" Icon={PlusIcon}>New recipe</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3">
        {demoRecipes.map((r) => (
          <motion.div key={r.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
            <div
              className="rounded-2xl border p-3 bg-white cursor-pointer"
              style={{ borderColor: "var(--border)" }}
              onClick={() => toggle(r.id)}
            >
              {/* Header */}
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-medium">{r.title}</div>
                  <div className="mt-0.5 text-xs text-[color:var(--text-subtle)]">{r.time} • {r.kcal} kcal</div>
                </div>
                <div className="flex items-center gap-1">
                  {r.hot && <Badge tone="a2">hot</Badge>}
                  {r.tags.map((t) => (
                    <Badge key={t} tone="a3"><TagIcon className="h-3 w-3" />{t}</Badge>
                  ))}
                </div>
              </div>

              {/* Expanded content */}
              {expanded === r.id && (
                <div className="mt-3">
                  <div className="text-sm font-medium mb-1">Ingredients</div>
                  <ul className="list-disc list-inside text-sm mb-2">
                    {r.ingredients.map((ing,i)=>(<li key={i}>{ing}</li>))}
                  </ul>
                  <div className="text-sm font-medium mb-1">Procedure</div>
                  <p className="text-sm mb-3">{r.procedure}</p>
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="a2">Edit</Button>
                    <Button size="sm" variant="danger">Delete</Button>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        ))}
      </div>
    </Card>
  );
}
```

**Notes:**
- Expansion is **single-open** (tracked by a single `expanded` id).  
- The card itself is the toggle target (`div` with `onClick`). If you prefer keyboard accessibility, wrap the header in a `button` and stop propagation on the action buttons when clicked.

### 4.6 Motion
- Use **framer-motion** only for the card’s fade/slide-in: `initial={{ opacity: 0, y: 6 }} → animate={{ opacity: 1, y: 0 }}` with `transition={{ duration: 0.2 }}`.
- No expanding/collapsing animation is required (instant show/hide is fine).

---

## 5) Accessibility & Interaction
- Text colors use `--text-subtle` for secondary metadata.
- Buttons must have accessible labels (the text content suffices here: “Edit”, “Delete”).
- If replacing the clickable `div` with a `button`, add `aria-expanded={expanded===id}` and keyboard handlers.
- Maintain 44px minimum tap targets where feasible.

---

## 6) “Website in General” Conventions
- **Radii:** `rounded-2xl` for cards & buttons.
- **Borders:** 1px using `--border` color.
- **Shadows:** subtle `shadow-sm` only.
- **Spacing:** container max width `max-w-7xl`, page padding `px-4 py-6`, grid gaps `gap-3`.
- **Typography:** default Tailwind font stack; titles medium weight; meta `text-xs`.- **Badges:** use `tone="a2"` for status (e.g., **hot**), `tone="a3"` for tags.- **Buttons:** variants `primary`, `danger`, `a1`, `a2`, `ghost` with sizes `sm | md | lg`.- **One-column rule for Recipes:** always `grid-cols-1` at all breakpoints.

---

## 7) Data Shapes (Temporary)
Use these shapes for local/demo state until a backend exists.

```ts
type Recipe = {
  id: number;
  title: string;
  time: string;       // e.g. "25 min"
  kcal: number;
  tags: string[];
  hot: boolean;
  ingredients: string[]; // for demo
  procedure: string;
};
```

---

## 8) Pages (titles only)
Create files/routes with the following titles and **no content** (blank body):

### Week Planner
### Shopping List
### Import/Export Database

---

## 9) Done Checklist (copy this into PRs)
- [ ] Tokens: container has all `--c-*` and `--text-*` CSS variables.
- [ ] Header & Sidebar match spec; Recipes is default active.
- [ ] Recipes page grid is single-column across breakpoints.
- [ ] Recipe card: title + meta + tags; *hot* badge when applicable.
- [ ] Clicking card expands ingredients + procedure; Edit (a2) & Delete (danger) on right.
- [ ] Motion on mount only (fade/slide-in).
- [ ] No “Plan/Remove” buttons exist on this page.

---

## 10) Copy/Paste Mini Snippets
```jsx
// Right-aligned actions in a card footer
<div className="flex justify-end gap-2">
  <Button size="sm" variant="a2">Edit</Button>
  <Button size="sm" variant="danger">Delete</Button>
</div>
```

```jsx
// Single-open expansion state
const [expanded, setExpanded] = useState(null);
const toggle = (id) => setExpanded(expanded === id ? null : id);
```

```jsx
// Single-column grid for recipe cards
<div className="grid grid-cols-1 gap-3">{/* cards */}</div>
```

---

## 11) Future Integration Notes (optional)
- Wire “New recipe” to a modal or new route.
- Replace `demoRecipes` with API data; keep the same property names to minimize refactors.
- Edit/Delete should stop event propagation so clicking them doesn’t toggle the card.

