# Anchor Edge Cases: no space after the hash

CommonMark allows the space after an ATX heading's opening `#` sequence to be
omitted: `#Setup`, `#5 bolt` and `#hashtag` are all real headings. GitHub slugs
them normally, so same-page anchors to those slugs must resolve. A run of
*seven* `#` (`####### not-a-heading`) is a paragraph, not a heading.

#Setup

A heading written as ``#Setup`` with no space after the hash.

##5 bolt

A heading whose text starts with a digit (CommonMark example 66).

###hashtag

A heading whose text begins with a second word-like token.

####### not-a-heading

Seven hashes is a paragraph -- it must never produce an anchor target.

Valid same-page links:

- [no-space heading](#setup)
- [digit-leading heading](#5-bolt)
- [hashtag heading](#hashtag)

Invalid same-page links:

- [seven hashes is not a heading](#not-a-heading)
- [missing](#nope)
