# Frontend Icon Contract

The frontend has two icon layers:

- `AppIcon` (`desktop/components/app-icon.vue`) is for applications, Dock items,
  desktop shortcuts, and product identity. Its catalog may resolve a native image
  asset; it owns the app tile fallback style.
- `SystemIcon` (`shared/components/system-icon.vue`) is for actions, menus,
  file operations, empty/error states, and other small interface affordances.

Use semantic `SystemIcon` names such as `download`, `folder-open`, `refresh`, or
`delete`. Do not import `lucide-vue-next` directly in shared or desktop icon
code. Import approved components from `shared/icons/lucide.ts`.

Legacy symbol and emoji aliases are intentionally kept in `SystemIcon` so existing
desktop context-menu data remains compatible during incremental migration. They
are compatibility input, not a new icon API.
