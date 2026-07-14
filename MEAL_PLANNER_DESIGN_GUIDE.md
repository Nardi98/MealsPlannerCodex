# Meal Planner — Frontend Design Guide

**Scope:** This guide specifies the *Recipes* page and site-wide conventions after
adopting the Claude Design **"meal-planner-app"** kit (project
`9497737e-33b6-4af2-b052-2a9f4aa47b24`). It is the source of truth for the shell,
the shared primitives, and the Recipes page.

**Status of other pages:** Meal Plan, Ingredients, Shopping List, and Import/Export
retain their **current implementation**. They inherit the new shell + tokens and
keep working through backward-compatible primitives; they will be migrated to the
new visual language in a later pass. The Shopping List spec at the end of this
file still describes intended behavior and remains valid.

> Stack: React + Vite, Tailwind (utility classes) + CSS-variable tokens,
> `@heroicons/react/24/outline`, a CDN-backed `Icon` for food glyphs.
> Fonts: **Sora** (display) + **Work Sans** (body) via Google Fonts.

---

## 1) Design Tokens (CSS variables)

All tokens live in [`frontend-v2/src/index.css`](frontend-v2/src/index.css) `:root`.
Components consume them via inline `style={{ ... 'var(--…)' }}` or arbitrary
Tailwind classes (e.g. `text-[color:var(--text-subtle)]`). The base `--c-*` /
`--text-*` values are also injected at runtime by
[`tokens.js`](frontend-v2/src/tokens.js) (`useCssVars`) to allow theming.

### Base palette (unchanged hex)
```css
--c-white: #F8FAF9;   --c-pos: #0C3A2D;   --c-neg: #BD210F;
--c-a1: #6D9773;      --c-a2: #FFB902;    --c-a3: #BB8A52;
--border: #e2e8f0;
--text-strong: #0C3A2D; --text-muted: #475569; --text-subtle: #64748b;
```

### Semantic aliases
```css
--surface-page: var(--c-white);   --surface-card: #FFFFFF;
--surface-sidebar: var(--c-pos);  --surface-sunken: #EEF3EF;
--border-default: var(--border);
--text-on-dark: #F8FAF9;          --text-on-accent: #121212;
--accent-primary: var(--c-a2);    --accent-secondary: var(--c-a1);
--accent-tertiary: var(--c-a3);   --success: var(--c-pos);  --danger: var(--c-neg);
--page-bg: #ECE6D9;   /* Bold theme warm-cream page background */
```

### Extended "category" palette
Warm, earthy hues for tags, ingredient categories, course tints, and nav icons.
**Never for core chrome.**
```css
--cat-terracotta: #D97B4F;  --cat-teal: #2F8F8A;  --cat-plum: #7A5A8C;
--cat-berry: #C4436B;       --cat-olive: #8A9A5B; --cat-sky: #4F86C6;
--cat-sun: var(--c-a2);     --cat-clay: var(--c-a3);
--cat-forest: var(--c-pos); --cat-sage: var(--c-a1);
```

### Typography
```css
--font-display: 'Sora', ui-sans-serif, system-ui, sans-serif;   /* headings, nav, buttons */
--font-body:    'Work Sans', ui-sans-serif, system-ui, sans-serif; /* body, inputs, data */
--text-xs: .75rem; --text-sm: .875rem; --text-base: 1rem; --text-lg: 1.125rem;
--text-xl: 1.25rem; --text-2xl: 1.5rem; --text-3xl: 2rem;
--weight-regular:400; --weight-medium:500; --weight-semibold:600; --weight-bold:700;
```
`body` uses `--font-body`; `h1–h4` use `--font-display`.

### Spacing, radius, shadow
```css
--space-1..12: 4/8/12/16/20/24/32/40/48px;
--radius-sm:8px; --radius-md:12px /* inputs, buttons */; --radius-lg:16px /* cards, modals */;
--radius-full:9999px /* chips, badges, avatars */;
--sidebar-width:224px;
--shadow-sm / --shadow-md / --shadow-lg;  /* green-tinted soft shadows */
```

---

## 2) Site-Wide Layout (Bold shell)

Implemented in [`frontend-v2/src/App.jsx`](frontend-v2/src/App.jsx). The whole app
sits on the warm-cream `--page-bg` with `padding: 20`.

- **Header:** logo left; right = search `Input` (decorative) + round `--c-a3`
  avatar stub. No bordered header — instead a subtle **gradient divider** line
  under it (`linear-gradient(...,color-mix(--c-pos 22%),...)`).
- **Sidebar:** a **dark forest-green (`--surface-sidebar`) rounded panel**, sticky,
  `--shadow-md`, `width: var(--sidebar-width)`. White text (`--text-on-dark`,
  Sora), **colored nav icons** per item, active item background
  `rgba(255,255,255,0.16)`. Items → routes:
  Recipes `/recipes` (berry), Meal Plan `/meal-plan` (gold), Ingredients
  `/ingredients` (olive), Shopping List `/shopping-list` (teal),
  Import/Export `/import-export` (plum).
- **Content frame:** a white `--surface-page` panel, `--radius-lg`, `--shadow-lg`,
  hairline `--border-default`, `padding: 24`, wrapping the routed page.

---

## 3) UI Primitives

All in [`frontend-v2/src/components/`](frontend-v2/src/components/), re-exported from
`components/index.js`.

- **`Button`** — variants `primary` (forest), `accent` (mustard, dark text),
  `secondary` (sage), `danger` (red), `ghost` (outline). Legacy aliases `a1`
  (=secondary) and `a2` (=accent) are retained. Sizes `sm|md|lg`. `--radius-md`,
  Sora. Icon passed as a **component** via the `Icon` prop.
- **`Badge`** — pill; background = tone color at 16% opacity, full-strength text.
  Tones accept legacy (`a1/a2/a3/pos/neg`), named (`forest/sage/gold/caramel/
  danger`), and category (`terracotta/teal/plum/berry/olive/sky`).
- **`Card`** — the single surface container: white, `--radius-lg`,
  `--border-default`, `--shadow-sm`. Merges an incoming `style` prop.
- **`Input`** — `--radius-md`, hairline border, mustard focus ring, Work Sans.
  Merges `style`.
- **`Icon`** — fetches + inlines raw SVG so `color` applies. `set="heroicons"`
  (default, outline/solid) or `set="mdi"` (Material Design Icons via Iconify) for
  **food/dish glyphs Heroicons lacks**. Loaded from CDN at runtime.
- **`Modal`** — full-screen scrim (`rgba(12,58,45,.55)`) + centered white `Card`
  with close button + title. Scrim click and close button both dismiss. Used by
  the Recipes detail dialog; bespoke form modals keep their own markup.

---

## 4) Recipes Page — Exact Spec

Implemented in [`frontend-v2/src/pages/RecipesPage.jsx`](frontend-v2/src/pages/RecipesPage.jsx),
wired to the real API (`recipesApi`, `tagsApi`, `ingredientsApi`).

### 4.1 Header
- Left: **Recipes** title (`--text-2xl`, Sora).
- Right: filter button (ghost, `FunnelIcon`, `aria-label="Filter"`) opening a
  popover with collapsible **Course / Tags / Ingredients** checkbox groups;
  search `Input` (`placeholder="Search recipes…"`); **New recipe** button
  (`variant="accent"`, `PlusIcon`).
- Filtering is client-side: title substring AND every selected tag AND every
  selected ingredient AND course ∈ selected courses.

### 4.2 Card Grid
- Responsive grid: `repeat(auto-fill, minmax(240px, 1fr))`, `gap: 16`.
- Each card (white surface, `--radius-lg`, `--shadow-sm`, hairline border) is
  **clickable** and opens the detail modal.
- **Media area** (`aspect-ratio 1/1`):
  - `<img alt="{title} photo">` when `recipe.image_url` is set;
  - otherwise a **course-colored placeholder tile** — a gradient from
    `courseColor[course]` with the **dish icon** centered.
  - Top-left: round white chip with the dish `Icon` in the course color.
  - Top-right: bulk-prep icon (`/assets/icons/bulk_icon.png`) when `recipe.hot`.
- **Body:** title (Sora, semibold), `course · N ingredients` (`--text-xs`,
  subtle), up to **2** tag `Badge`s (`tone="caramel"`).

### 4.3 Detail Modal (on click)
Uses the shared `Modal`: 16:9 media (image or placeholder), course line with dish
icon, bulk + tag badges, **Ingredients** list (`amount unit name`), **Procedure**,
and right-aligned **Edit** (`accent`) / **Delete** (`danger`). Edit opens
`NewRecipeModal` prefilled; Delete calls `recipesApi.delete`.

### 4.4 Dish iconography & course colors
Defined in [`frontend-v2/src/constants/recipeIcons.js`](frontend-v2/src/constants/recipeIcons.js):
- `courseColor`: main→terracotta, side→olive, first-course→sky, dessert→berry.
- `dishIcon(recipe)`: title keyword override (pasta→noodles, soup/stew→pot,
  salad→leaf, sandwich/toast→baguette) else `COURSE_ICONS[course]` else
  `silverware-fork-knife`. Rendered with `Icon set="mdi"`.

### 4.5 New/Edit recipe form
`NewRecipeModal` includes an optional **Image URL** field, threaded through
`recipesApi` (`serialiseRecipe`/`normaliseRecipe`) to the backend `image_url`.

---

## 5) Backend note — `image_url`

Recipes carry an optional `image_url` (`models.Recipe`, `schemas.RecipeIn/Out`,
threaded through `crud` create/update/import/export). Absent → the Recipes UI
renders the course-colored placeholder tile.

---

## 6) "Website in General" Conventions
- **Radii:** `--radius-lg` for cards & modals, `--radius-md` for inputs & buttons,
  `--radius-full` for chips/badges/avatars.
- **Borders:** 1px `--border-default`. **Shadows:** `--shadow-sm/md/lg` only.
- **Surfaces:** white cards on the cream `--page-bg`; the green sidebar and the
  framed content panel define the shell.
- **Color discipline:** core chrome stays restrained (greens, golds, neutrals);
  the category palette adds color only on tags, categories, course tints, nav icons.
- **Typography:** Sora for titles/nav/buttons, Work Sans for body/inputs.

---

# Shopping List Page — Exact Spec

> Purpose: pick a date range, see covered days on compact calendars, select
> recipes, and export a deduplicated, checkable shopping list as `.txt`.
> (Current implementation retained; will migrate to the new visual language later.)

## Layout Overview
```
[ Page Header ]  — Title: “Shopping List” · Date inputs: Begin | End
[ Calendars Row ] — 3 mini month grids (month of Begin date + next two)
[ Two Columns ]
  Left:  Recipes (title + ingredient count)
  Right: Ingredients (deduped) + Export (only unchecked items)
```

## Page Header
- Title: **Shopping List**. Two native date inputs: **Begin** and **End**.
- Range is inclusive; if `start > end`, adjust the other end so `start <= end`.

## Calendars Row
- Three months from the Begin date. Week starts Monday. Day numbers only.
- Month label under each grid (`MMMM yyyy`).
- **Range indicator:** green capsule under in-range days (`h-1 w-6 rounded-full`,
  `background-color: var(--c-a1)`).

## Two Columns
- **Left — Recipes:** title (bold) + ingredient count (subtle).
- **Right — Ingredients:** **Export** button (`accent`/gold) in header; list built
  by **deduplicating** across selected recipes (case-insensitive, trimmed). Each
  row is clickable (line-through + filled square via `--c-a1`). Export downloads
  `shopping-list_YYYYMMDD_YYYYMMDD.txt` with only unchecked items.

### Reference snippets
```jsx
const buildShoppingList = (recipes) => {
  const seen = new Set(); const list = [];
  recipes.forEach((r) => r.ingredients.forEach((ing) => {
    const key = ing.trim().toLowerCase();
    if (!seen.has(key)) { seen.add(key); list.push({ id: key.replace(/[^a-z0-9]+/g, '-'), label: ing }); }
  }));
  return list;
};
```
```jsx
import { format } from 'date-fns';
const formatExportText = (items, crossed, start, end) => [
  `Shopping List (${format(start,'yyyy-MM-dd')} → ${format(end,'yyyy-MM-dd')})`, '',
  ...items.filter((i) => !crossed.has(i.id)).map((i) => `• ${i.label}`),
].join('\n');
```

## Accessibility
- Ingredient rows keyboard-reachable (`role="button"`, `tabIndex=0`, Enter/Space,
  `aria-pressed`). Date inputs have visible labels.

---

## 7) Done Checklist (copy into PRs)
- [ ] `index.css` has the full token set (base + semantic + category + type +
      spacing + shadow) and the Sora/Work Sans `@import`.
- [ ] Bold shell: cream page, green sticky sidebar with colored icons, gradient
      divider, framed white content panel.
- [ ] Primitives updated & backward-compatible (Button accent/secondary + a1/a2,
      Badge category tones, Card/Input merge `style`, new `Icon` + `Modal`).
- [ ] Recipes: image-card grid (`auto-fill minmax(240px)`), placeholder tile when
      no `image_url`, dish icon + bulk badge, click → detail modal with Edit/Delete.
- [ ] `image_url` round-trips backend↔frontend; New/Edit form exposes it.
- [ ] Other four pages still render inside the new shell.
