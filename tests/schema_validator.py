"""Minimal, dependency-free JSON Schema (draft 2020-12 subset) validator.

ARCHITECTURE_v1.md section 6.3 requires that ``--json`` and ``--sarif`` reports
be validated against the vendored schemas under ``schemas/`` **without** pulling
in the third-party ``jsonschema`` package. This module is a ~130-line subset
validator used *only by the test suite* (it is not part of the shipped runtime
path).

Supported keywords (the subset the two vendored schemas actually use):
  * ``type``                -- string or list of strings, incl. ``"null"``
  * ``required``            -- list of required object properties
  * ``properties``          -- per-property sub-schema
  * ``items``               -- sub-schema applied to every array element
  * ``enum``                -- value must be one of the listed values
  * ``const``               -- value must equal the given value
  * ``$schema`` / ``$id`` / ``title`` / ``description`` -- ignored metadata

Anything outside this subset is ignored rather than treated as an error, so the
validator stays small while covering every construct in the vendored schemas.
"""

# JSON ``type`` keyword -> predicate for the Python values JSON maps onto.
_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}

# Metadata-only keywords carry no validation semantics.
_IGNORED_KEYWORDS = frozenset(
    ("$schema", "$id", "title", "description", "default", "examples")
)


def _type_name(value):
    """Return a JSON-schema type name for ``value`` (for error messages)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def validate(instance, schema, path="$"):
    """Validate ``instance`` against ``schema``.

    :param instance: the decoded JSON value to check.
    :param schema: the decoded JSON Schema (subset) to check against.
    :param path: JSON pointer-ish path used in error messages.
    :returns: a list of human-readable error strings (empty when valid).
    """
    errors = []

    if not isinstance(schema, dict):
        # A boolean schema is legal JSON Schema; treat True as "accept".
        return errors

    # --- type -----------------------------------------------------------------
    expected = schema.get("type")
    if expected is not None:
        names = expected if isinstance(expected, list) else [expected]
        if not any(_TYPE_CHECKS.get(n, lambda v: True)(instance) for n in names):
            errors.append(
                "%s: expected type %s, got %s"
                % (path, "/".join(names), _type_name(instance))
            )
            # Sub-keyword checks below assume the type matched; bail out early.
            return errors

    # --- enum / const ---------------------------------------------------------
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(
            "%s: %r is not one of %r" % (path, instance, schema["enum"])
        )
    if "const" in schema and instance != schema["const"]:
        errors.append(
            "%s: expected const %r, got %r" % (path, schema["const"], instance)
        )

    # --- object ---------------------------------------------------------------
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append("%s: missing required property %r" % (path, key))
        properties = schema.get("properties", {})
        for key, sub_schema in properties.items():
            if key in instance:
                errors.extend(
                    validate(instance[key], sub_schema, "%s.%s" % (path, key))
                )

    # --- array ----------------------------------------------------------------
    if isinstance(instance, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, element in enumerate(instance):
                errors.extend(
                    validate(element, item_schema, "%s[%d]" % (path, index))
                )

    return errors


def is_valid(instance, schema):
    """Convenience predicate: True when ``instance`` matches ``schema``."""
    return not validate(instance, schema)
