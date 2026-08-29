/**
 * The marker for a meal cooked in bulk earlier in the week. Both calendar
 * layouts show it beside the recipe title, so the alt text and sizing live in
 * one place rather than being retyped per layout.
 */
export default function LeftoverIcon() {
  return (
    <img
      src="/assets/icons/left_overs_icon.png"
      alt="Leftover"
      className="inline ml-1 h-4 w-4"
    />
  )
}
