# Frontend v2

This React app communicates with the Meal Planner API. When generating a
meal plan you can enable a temporary *Download debug log* option on the form
to receive a `plan-debug-log.txt` file containing the scoring breakdown for
each recipe.

The project uses [Vite](https://vitejs.dev/) for development and includes
ESLint and Vitest for linting and unit tests.

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript
with type-aware lint rules enabled. Check out the
[TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts)
for information on how to integrate TypeScript and
[`typescript-eslint`](https://typescript-eslint.io) in your project.
