import { ArchiveBoxIcon, ArrowDownTrayIcon, PlusIcon } from '@heroicons/react/24/outline'
import { Button } from '../Button'

/**
 * The library admin's controls on Discover (UI-12). The page mounts this only
 * for an admin, so nobody else gets so much as a hidden node (UI-11).
 *
 * "Show retired" is a two-state switch (`aria-pressed`) between browsing the
 * published library and the admin listing of every entry.
 */
export default function CatalogAdminToolbar({ showRetired, exporting, onNew, onToggleRetired, onExport }) {
  return (
    <div
      role="group"
      aria-label="Library admin"
      className="flex flex-wrap items-center gap-2 border-t pt-3"
      style={{ borderColor: 'var(--border-default)' }}
    >
      <span
        className="w-full md:w-auto"
        style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 'var(--weight-semibold)',
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          color: 'var(--text-subtle)',
        }}
      >
        Library admin
      </span>
      <Button variant="secondary" Icon={PlusIcon} onClick={onNew}>
        New catalog recipe
      </Button>
      <Button variant="ghost" Icon={ArchiveBoxIcon} aria-pressed={showRetired} onClick={onToggleRetired}>
        Show retired
      </Button>
      <Button variant="ghost" Icon={ArrowDownTrayIcon} disabled={exporting} onClick={onExport}>
        {exporting ? 'Exporting…' : 'Export'}
      </Button>
    </div>
  )
}
