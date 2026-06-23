# @emo Autocomplete — Design Spec

**Date:** 2026-06-23
**Status:** Approved (pending written review)
**Branch:** `feat/emoji-autocomplete` (new, off `main` — `main` already contains the custom-emoji-placeholders + thumbnail features).

## Summary

Add an @-mention–style autocomplete to the dashboard's free-text authoring fields. Typing `@emo` opens a popup at the text caret listing the configured emoji placeholders (with their thumbnail previews); selecting one replaces the `@emo…` trigger with the real `{emo:<id>}` token. This makes inserting emoji tokens fast and visual instead of requiring the admin to remember ids.

Reality the design accepts: a `<textarea>` cannot render the emoji inline, so after insertion the field shows the literal `{emo:5}` token text — which is exactly what is saved and what the bot renders. The autocomplete is an input aid, not a WYSIWYG editor.

## Decisions (locked during brainstorming)

- **Scope:** all token-eligible free-text fields (multi-line `Textarea`s): the Notifications message composer (`notif-msg`), Products description + upgrade-request text, and BotUiSettings `product_choose_text` / `variation_choose_text` / `upload_notification_header`. Chat-ID textareas are excluded (not emoji-eligible). Single-line product/variation **name** inputs are out of scope for v1.
- **Trigger / insert:** `@emo` opens the list; **contiguous** trailing word characters (no spaces) form a live filter query — e.g. `@emoheader` filters by "header" — so the trigger has a clear, unambiguous end. Selecting replaces the `@emo<query>` span with `{emo:<id>}`.
- **Popup position:** anchored at the text caret (mirror-div caret-coordinate measurement).
- **Data:** placeholders from the existing `GET /api/emoji-placeholders` (returns `{id, name, token, units}`); no API change.

## Components

### 1. `EmojiAutocompleteTextarea` (new)
`frontend/src/shared/components/EmojiAutocompleteTextarea.tsx`. A thin wrapper around the shared `<Textarea>` accepting the SAME props (`value`, `onChange`, `id`, `rows`, `autoResize`, `placeholder`, …) so it is a drop-in replacement. Responsibilities:
- Hold a ref to the underlying `<textarea>`.
- On change/keyup/click, run trigger detection against the text before the caret; manage popup open state + the current query + highlighted index.
- Render the suggestion popup in a portal positioned at the caret.
- On select, perform the token insertion and propagate via `onChange`.

### 2. Pure helpers (testable without DOM)
In the same module (or a sibling `emojiAutocomplete.ts`):
- `matchTrigger(textBeforeCaret: string) -> { query: string, start: number } | null` — regex `/@emo([\p{L}\p{N}_]*)$/u`; `start` is the index of the `@`.
- `insertToken(value: string, caret: number, matchStart: number, token: string) -> { value: string, caret: number }` — replaces `value[matchStart..caret]` with `token`; returns the new value and the caret position after the token.

### 3. `getCaretCoordinates` util (new)
`frontend/src/shared/lib/caretCoordinates.ts`: the standard mirror-div technique. Builds a hidden `<div>` cloning the textarea's relevant computed styles (font, padding, border, width, white-space, word-wrap), fills it with `value[0..caret]` plus a marker `<span>`, measures the span's `offsetTop/offsetLeft`, and returns `{ top, left, height }` relative to the textarea, accounting for `scrollTop`/`scrollLeft`. The popup is positioned at the textarea's bounding rect + these offsets, placing it just below the caret line.

### 4. Suggestion popup
Reuses the established popup pattern (portal + `useDismiss` + getBoundingClientRect-style positioning, as in `Select`). Each row renders the placeholder's `EmojiPreview` (thumbnails, from the just-built component) + `name` + a greyed `{emo:id}` token. Keyboard: ↑/↓ move the highlight, Enter/Tab insert the highlighted item, Esc closes; mouse hover sets the highlight, click inserts. Empty state when no placeholders match ("No emoji placeholders — create one on the Emoji page").

### 5. Data
Placeholders are fetched from `GET /api/emoji-placeholders` lazily on the first `@emo` open and cached in component state (admin-only pages, low volume). No new endpoint.

## Insertion mechanics (controlled component)

The fields are controlled (`value` + native `onChange`). On select:
1. Compute `{ value: newValue, caret }` via `insertToken`.
2. Set the textarea DOM value and `setSelectionRange(caret, caret)` so the cursor lands after the inserted token.
3. Fire the parent `onChange` with a synthetic event whose `target` is the textarea (so `e.target.value === newValue`) — every existing consumer reads only `e.target.value` (`e => setMessage(e.target.value)`, `e => setFormData(d => ({...d, description: e.target.value}))`, etc.), so this integrates without changing any page handler.
4. Close the popup.

## Wiring

Swap `<Textarea …/>` → `<EmojiAutocompleteTextarea …/>` (props unchanged, still inside their `FormField` wrappers) at:
- `frontend/src/pages/NotificationsPage.tsx` — the message composer (`notif-msg`).
- `frontend/src/pages/ProductsPage.tsx` — description (`-desc`) and upgrade-request text (`-upgrade`).
- `frontend/src/pages/BotUiSettingsPage.tsx` — `product_choose_text`, `variation_choose_text`, `upload_notification_header`.

## Error handling & edge cases

- Placeholder fetch fails → popup shows an empty/error state; typing is never blocked; field still works as a plain textarea.
- No `@emo` match → popup closed; the component behaves byte-for-byte like a plain `Textarea` (zero behavior change when the feature isn't triggered).
- Textarea scroll / autoResize → handled by subtracting `scrollTop`/`scrollLeft` in the caret math.
- Multiple autocomplete fields on one page each own their popup state independently.
- Selecting with the keyboard must not also insert a newline (Enter is consumed when the popup is open and an item is highlighted).

## Testing

- **Pure helpers:** `matchTrigger` (matches `@emo`, captures query, returns null when absent, handles mid-text carets) and `insertToken` (replaces the right span, computes caret) — unit-tested, no DOM.
- **Component (vitest + @testing-library/react):** typing `@emo` opens the list; typing a query filters it; selecting (click and Enter) inserts `{emo:<id>}` and fires `onChange` with the new value; Esc closes without inserting; when not triggered, the field passes text through normally.
- **Not unit-tested:** caret pixel geometry (jsdom has no layout) — verified manually in `npm run build` + a live check. Mock `/api/emoji-placeholders` in component tests.
- Run with `CI=true npx vitest run`.

## Out of scope (v1)

- Single-line `<input>` fields (product/variation name).
- Inline/WYSIWYG rendering of the emoji inside the textarea (the field shows the `{emo:id}` token text).
- A separate live-preview strip showing the composed message with rendered thumbnails (possible later enhancement).
- Backend changes (none — reuses the existing placeholders endpoint).
