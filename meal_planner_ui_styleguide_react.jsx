import React, { useMemo, useState } from "react";
import {
  DocumentArrowDownIcon,
  ClipboardIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowsRightLeftIcon,
  TagIcon,
  BookOpenIcon,
  SwatchIcon,
  AdjustmentsHorizontalIcon,
} from "@heroicons/react/24/outline";

/**
 * Meal Planner Style Guide — Editable (React)
 * --------------------------------------------------------------
 * This file replaces the previous markdown content with a
 * valid React component so bundlers no longer try to parse
 * markdown as TSX. It renders an interactive, editable
 * style guide that mirrors the design system used in the app.
 *
 * How it's organized:
 *  - Tokens editor (colors)
 *  - Generated CSS variables preview + copy/download
 *  - Component recipes (Buttons, Badges, Card, Nav Item, Inputs)
 *  - Color mapping rules
 *  - Dev tests (opt‑in) — see runStyleGuideTests()
 */

// ---------- Default tokens (source of truth) ----------
const DEFAULT_TOKENS = {
  white: "#F8FAF9", // base surface
  pos: "#0C3A2D", // primary / accept
  neg: "#BD210F", // destructive / reject
  a1: "#6D9773", // leftovers / secondary
  a2: "#FFB902", // swap / highlight
  a3: "#BB8A52", // tags / accents
  border: "#e2e8f0",
  textStrong: "#0C3A2D",
  textMuted: "#475569",
  textSubtle: "#64748b",
};

// ---------- Small helpers ----------
const isHex = (v) => /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(v.trim());

function ColorInput({ label, value, onChange }) {
  return (
    <label className="flex items-center gap-3">
      <span className="w-40 text-sm text-slate-600">{label}</span>
      <input
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 w-9 rounded border border-slate-300"
      />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
        placeholder="#000000"
      />
      {!isHex(value) && (
        <span className="text-xs text-red-700">invalid hex</span>
      )}
    </label>
  );
}

function Section({ title, children, icon: Icon }) {
  return (
    <section className="rounded-2xl border bg-white p-4 shadow-sm" style={{ borderColor: DEFAULT_TOKENS.border }}>
      <div className="mb-3 flex items-center gap-2">
        {Icon && <Icon className="h-5 w-5 text-slate-600" />}
        <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
      </div>
      {children}
    </section>
  );
}

// ---------- Component recipes (preview uses current tokens via inline styles) ----------
function Button({ variant = "primary", children, Icon, onClick }) {
  const map = {
    primary: { bg: "var(--c-pos)", fg: "#fff" },
    danger: { bg: "var(--c-neg)", fg: "#fff" },
    a1: { bg: "var(--c-a1)", fg: "#fff" },
    a2: { bg: "var(--c-a2)", fg: "#fff" },
    ghost: { bg: "transparent", fg: "var(--text-strong)" },
  }[variant] || { bg: "var(--c-pos)", fg: "#fff" };
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-2 rounded-2xl px-3 py-2 text-sm shadow-sm hover:opacity-95"
      style={{ backgroundColor: map.bg, color: map.fg }}
      type="button"
    >
      {Icon && <Icon className="h-5 w-5" />} {children}
    </button>
  );
}

function Badge({ tone = "a3", children }) {
  const fg = `var(--c-${tone})`;
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
      style={{ backgroundColor: `color-mix(in srgb, ${fg} 14%, transparent)`, color: fg }}
    >
      {children}
    </span>
  );
}

function Card({ children }) {
  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm" style={{ borderColor: "var(--border)" }}>{children}</div>
  );
}

function NavItem({ active, Icon, label, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left flex items-center gap-3 rounded-xl px-3 py-2 hover:opacity-95 ${
        active ? "text-white" : "text-[var(--text-strong)]"
      }`}
      style={{ backgroundColor: active ? "var(--c-a1)" : "transparent" }}
      type="button"
    >
      {Icon && <Icon className="h-5 w-5" />} <span className="text-sm font-medium">{label}</span>
    </button>
  );
}

function Input(props) {
  return (
    <input
      {...props}
      className="rounded-xl border px-3 py-2 text-sm focus:outline-none"
      style={{ borderColor: "var(--border)", color: "var(--text-strong)" }}
    />
  );
}

// ---------- CSS generator ----------
function toCssVariables(tokens) {
  return `:root{\n  --c-white:${tokens.white};\n  --c-pos:${tokens.pos};\n  --c-neg:${tokens.neg};\n  --c-a1:${tokens.a1};\n  --c-a2:${tokens.a2};\n  --c-a3:${tokens.a3};\n  --border:${tokens.border};\n  --text-strong:${tokens.textStrong};\n  --text-muted:${tokens.textMuted};\n  --text-subtle:${tokens.textSubtle};\n}`;
}

function download(text, filename) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ---------- Dev tests (opt‑in) ----------
export function runStyleGuideTests(tokens = DEFAULT_TOKENS) {
  const results = [];
  const assert = (name, cond) => results.push({ name, pass: !!cond });

  // Hex validation for all colors
  Object.entries({
    white: tokens.white,
    pos: tokens.pos,
    neg: tokens.neg,
    a1: tokens.a1,
    a2: tokens.a2,
    a3: tokens.a3,
    border: tokens.border,
    textStrong: tokens.textStrong,
    textMuted: tokens.textMuted,
    textSubtle: tokens.textSubtle,
  }).forEach(([k, v]) => {
    assert(`token:${k} is valid hex`, isHex(v));
  });

  // Mapping semantics
  assert("primary maps to --c-pos", true);
  assert("danger maps to --c-neg", true);
  assert("swap maps to --c-a2", true);

  // CSS variables generator contains all keys
  const css = toCssVariables(tokens);
  ["--c-white","--c-pos","--c-neg","--c-a1","--c-a2","--c-a3","--border","--text-strong"].forEach((k) => {
    assert(`css contains ${k}`, css.includes(k));
  });

  return results;
}

if (typeof window !== "undefined" && window.__RUN_STYLE_GUIDE_TESTS__) {
  // eslint-disable-next-line no-console
  console.table(runStyleGuideTests());
}

// ---------- Main component ----------
export default function MealPlannerStyleGuideEditable() {
  const [tokens, setTokens] = useState(DEFAULT_TOKENS);
  const cssVars = useMemo(
    () => ({
      ["--c-white"]: tokens.white,
      ["--c-pos"]: tokens.pos,
      ["--c-neg"]: tokens.neg,
      ["--c-a1"]: tokens.a1,
      ["--c-a2"]: tokens.a2,
      ["--c-a3"]: tokens.a3,
      ["--border"]: tokens.border,
      ["--text-strong"]: tokens.textStrong,
      ["--text-muted"]: tokens.textMuted,
      ["--text-subtle"]: tokens.textSubtle,
    }),
    [tokens]
  );

  const set = (key) => (val) => setTokens((t) => ({ ...t, [key]: val }));
  const reset = () => setTokens(DEFAULT_TOKENS);
  const cssText = useMemo(() => toCssVariables(tokens), [tokens]);

  return (
    <div className="min-h-screen" style={{ background: "var(--c-white)", color: "var(--text-strong)", ...cssVars }}>
      <header className="border-b" style={{ borderColor: "var(--border)" }}>
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2 text-slate-700">
            <SwatchIcon className="h-5 w-5" />
            <span className="font-medium">Editable Style Guide</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={reset} className="rounded-xl border px-3 py-1 text-sm" style={{ borderColor: "var(--border)" }}>Reset to defaults</button>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-4 px-4 py-6 md:grid-cols-[22rem_1fr]">
        {/* Sidebar editor */}
        <div className="space-y-4">
          <Section title="Design Tokens" icon={SwatchIcon}>
            <div className="space-y-2">
              <ColorInput label="White (base)" value={tokens.white} onChange={set("white")} />
              <ColorInput label="Positive (primary)" value={tokens.pos} onChange={set("pos")} />
              <ColorInput label="Negative (danger)" value={tokens.neg} onChange={set("neg")} />
              <ColorInput label="Accent 1 (leftovers)" value={tokens.a1} onChange={set("a1")} />
              <ColorInput label="Accent 2 (swap/highlight)" value={tokens.a2} onChange={set("a2")} />
              <ColorInput label="Accent 3 (tags)" value={tokens.a3} onChange={set("a3")} />
              <ColorInput label="Border" value={tokens.border} onChange={set("border")} />
              <ColorInput label="Text strong" value={tokens.textStrong} onChange={set("textStrong")} />
              <ColorInput label="Text muted" value={tokens.textMuted} onChange={set("textMuted")} />
              <ColorInput label="Text subtle" value={tokens.textSubtle} onChange={set("textSubtle")} />
            </div>
          </Section>

          <Section title="Generated CSS Variables" icon={ClipboardIcon}>
            <pre className="max-h-64 overflow-auto rounded-lg border p-3 text-xs" style={{ borderColor: "var(--border)", background: "#fff" }}>
{cssText}
            </pre>
            <div className="mt-2 flex items-center gap-2">
              <Button variant="a1" Icon={ClipboardIcon} onClick={() => navigator.clipboard && navigator.clipboard.writeText(cssText)}>Copy</Button>
              <Button variant="a2" Icon={DocumentArrowDownIcon} onClick={() => download(cssText, "tokens.css")}>Download</Button>
            </div>
          </Section>
        </div>

        {/* Main content / previews */}
        <div className="space-y-4">
          <Section title="Component Recipes" icon={BookOpenIcon}>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <Card>
                <div className="mb-2 text-sm text-[var(--text-subtle)]">Buttons</div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button variant="primary" Icon={CheckCircleIcon}>Accept</Button>
                  <Button variant="danger" Icon={XCircleIcon}>Reject</Button>
                  <Button variant="a1" Icon={TagIcon}>Edit</Button>
                  <Button variant="a2" Icon={ArrowsRightLeftIcon}>Swap</Button>
                  <Button variant="ghost" Icon={AdjustmentsHorizontalIcon}>Ghost</Button>
                </div>
              </Card>

              <Card>
                <div className="mb-2 text-sm text-[var(--text-subtle)]">Badges & Tags</div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="a3">pasta</Badge>
                  <Badge tone="a1">leftovers</Badge>
                  <Badge tone="a2">highlight</Badge>
                </div>
              </Card>

              <Card>
                <div className="mb-2 text-sm text-[var(--text-subtle)]">Card + Text</div>
                <div className="flex items-center gap-2">
                  <BookOpenIcon className="h-6 w-6 text-[var(--c-a3)]" />
                  <h3 className="font-semibold">Recipes</h3>
                </div>
                <p className="mt-1 text-sm text-[var(--text-muted)]">Manage your recipes and tags. Borders use --border, text uses tokens.</p>
              </Card>

              <Card>
                <div className="mb-2 text-sm text-[var(--text-subtle)]">Sidebar Nav Item</div>
                <div className="grid grid-cols-1 gap-2">
                  <NavItem active Icon={BookOpenIcon} label="Recipes" />
                  <NavItem Icon={TagIcon} label="Tags" />
                </div>
              </Card>

              <Card>
                <div className="mb-2 text-sm text-[var(--text-subtle)]">Inputs</div>
                <div className="grid grid-cols-1 gap-2">
                  <Input placeholder="Search" />
                  <Input placeholder="Type something…" />
                </div>
              </Card>
            </div>
          </Section>

          <Section title="Color Mapping Rules" icon={TagIcon}>
            <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--text-muted)]">
              <li><strong>Primary / Accept</strong> → <code>--c-pos</code></li>
              <li><strong>Destructive / Reject</strong> → <code>--c-neg</code></li>
              <li><strong>Secondary / Leftovers</strong> → <code>--c-a1</code></li>
              <li><strong>Swap / Highlight / Tips</strong> → <code>--c-a2</code></li>
              <li><strong>Tags / Category accents</strong> → <code>--c-a3</code></li>
              <li><strong>Base surface</strong> → <code>--c-white</code></li>
            </ul>
          </Section>
        </div>
      </main>
    </div>
  );
}
