# Anchor Edge Cases: headings hidden inside HTML comments

GitHub does not parse the *contents* of a block-level HTML comment as
Markdown, so a heading written inside ``<!-- ... -->`` produces **no** anchor
target. This file offers both a real heading and comment-hidden heading-like
lines that must NOT resolve as anchors.

## Visible Heading

A real, renderable heading -- the anchor `#visible-heading` resolves.

<!--
## Hidden Heading

This whole block is an HTML comment. GitHub renders none of it, so
`#hidden-heading` is a broken same-page anchor even though the text looks
exactly like the visible heading above.
-->

## After Comment

A heading that follows a terminated comment on its own line.

Valid same-page links:

- [visible heading](#visible-heading)
- [after comment](#after-comment)

Invalid same-page links (headings live inside the comment):

- [hidden heading](#hidden-heading)
