# Anchor Collision Edge Cases

Cross-heading slug collisions (github-slugger parity).

Two sections share the base slug ``setup`` and a third heading literally
spells the suffixed slug ``setup-1``. GitHub's slugger emits
``setup``, ``setup-1``, ``setup-1-1`` -- it never yields a duplicate slug.

## Setup

First setup section.

## Setup

Second (duplicate) setup section.

## Setup 1

A heading whose literal text is already ``Setup 1``.

Valid same-page links:

- [base slug](#setup)
- [first disambiguated slug](#setup-1)
- [collision-avoiding slug](#setup-1-1)

Invalid same-page links:

- [bogus second suffix](#setup-1-2)
- [never emitted](#setup-2)
