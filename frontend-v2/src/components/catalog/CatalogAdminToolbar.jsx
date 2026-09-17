import { ArrowDownTrayIcon, PlusIcon } from '@heroicons/react/24/outline'
import { Button } from '../Button'
import { Input } from '../Input'
import RecipeSort from '../RecipeSort'

/**
 * The library admin's one control bar: the two authoring actions on the left,
 * and the three controls that narrow the listing on the right.
 *
 * Search, status and sort all run server-side, like the browse listing's, so
 * each is a plain value handed back up and nothing here filters rows itself.
 * There is no "show retired" switch any more -- the admin listing shows every
 * entry and the status filter is how you look at one state at a time.
 */
export default function CatalogAdminToolbar({
  search,
  status,
  sort,
  sortOptions,
  exporting,
  onSearch,
  onStatus,
  onSort,
  onNew,
  onExport,
}) {
  return (
    <div
      role="group"
      aria-label="Library admin"
      className="flex flex-wrap items-center gap-2 border-t pt-3"
      style={{ borderColor: 'var(--border-default)' }}
    >
      <Button variant="secondary" Icon={PlusIcon} onClick={onNew}>
        New catalog recipe
      </Button>
      <Button variant="ghost" Icon={ArrowDownTrayIcon} disabled={exporting} onClick={onExport}>
        {exporting ? 'Exporting…' : 'Export'}
      </Button>

      <div className="flex w-full flex-wrap items-center gap-2 md:ml-auto md:w-auto">
        <Input
          placeholder="Search the library…"
          aria-label="Search the library"
          className="min-w-0 flex-1 md:w-56 md:flex-none"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
        />
        <Input
          as="select"
          aria-label="Filter by status"
          value={status}
          onChange={(e) => onStatus(e.target.value)}
        >
          <option value="">All entries</option>
          <option value="published">Published</option>
          <option value="retired">Retired</option>
        </Input>
        <RecipeSort sortKey={sort} options={sortOptions} showDirection={false} onChange={onSort} />
      </div>
    </div>
  )
}
