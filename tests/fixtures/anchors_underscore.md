# Anchor Edge Cases: underscores in headings

GitHub's heading slugger treats ``_`` as a word character: an intraword
underscore survives verbatim in the generated anchor. The heading
``## foo_bar`` therefore yields the anchor ``#foo_bar`` (not ``#foobar``). A
same-page link to ``#foo_bar`` must resolve, while the underscore-stripped
``#foobar`` is not a real target.

This is the concrete regression the underscore-preserving slug fixes: a naive
slugifier that peels every ``_`` (as if it were an emphasis marker) computes
``foobar`` and so reports the perfectly valid ``#foo_bar`` link as broken.

## foo_bar

A heading with an intraword underscore.

## config_file_path

A snake_case heading whose anchor keeps every underscore.

## mixed - foo_bar baz

An underscore sitting next to hyphens and spaces.

Valid same-page links:

- [intraword underscore](#foo_bar)
- [snake case](#config_file_path)
- [mixed](#mixed---foo_bar-baz)

Invalid same-page links (the underscore was wrongly stripped by a naive slug):

- [underscore dropped from foo_bar](#foobar)
- [underscore dropped from snake case](#configfilepath)
