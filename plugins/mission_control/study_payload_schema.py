"""Small, bounded JSON Schema subset for domain-owned exercise data contracts.

Only closed objects, bounded arrays and bounded strings are supported. Unsupported
keywords fail before research; no remote references or optional validator dependency.
"""


def payload_schema(brief):
    if 'payload_schema' not in brief:
        return None
    schema = brief['payload_schema']
    _schema_node(schema, 0)
    if schema['type'] != 'object':
        raise ValueError('curriculum payload schema root must be an object')
    return schema


def _bounds(schema, low, high, maximum):
    lower, upper = schema[low], schema[high]
    if type(lower) is not int or type(upper) is not int or not 0 <= lower <= upper <= maximum:
        raise ValueError('curriculum payload schema has invalid bounds')


def _object_schema(schema, depth):
    properties, required = schema['properties'], schema['required']
    if (schema['additionalProperties'] is not False or not isinstance(properties, dict)
            or not 1 <= len(properties) <= 32 or not isinstance(required, list)
            or any(not isinstance(key, str) or not 1 <= len(key) <= 120 for key in properties)
            or any(not isinstance(key, str) for key in required)
            or len(required) != len(properties) or set(required) != set(properties)):
        raise ValueError('curriculum payload schema objects must declare and require every property')
    for child in properties.values():
        _schema_node(child, depth + 1)


def _schema_node(schema, depth):
    keys = {'object': {'type', 'properties', 'required', 'additionalProperties'},
            'array': {'type', 'items', 'minItems', 'maxItems'},
            'string': {'type', 'minLength', 'maxLength'}}
    if not isinstance(schema, dict) or depth > 6 or not isinstance(schema.get('type'), str):
        raise ValueError('curriculum payload schema is invalid or exceeds nesting limit')
    kind = schema['type']
    if kind not in keys or set(schema) != keys[kind]:
        raise ValueError('curriculum payload schema uses unsupported types or keywords')
    if kind == 'object':
        _object_schema(schema, depth)
    elif kind == 'array':
        _bounds(schema, 'minItems', 'maxItems', 35)
        _schema_node(schema['items'], depth + 1)
    else:
        _bounds(schema, 'minLength', 'maxLength', 8000)


def validate_payload(value, schema):
    """Check every supported constraint even when provider schema checks are absent."""
    kind = schema['type']
    if kind == 'object':
        if not isinstance(value, dict) or set(value) != set(schema['properties']):
            raise ValueError('curriculum payload does not match its declared object properties')
        for key, child in schema['properties'].items():
            validate_payload(value[key], child)
    elif kind == 'array':
        if not isinstance(value, list) or not schema['minItems'] <= len(value) <= schema['maxItems']:
            raise ValueError('curriculum payload does not match its declared array bounds')
        for item in value:
            validate_payload(item, schema['items'])
    elif not isinstance(value, str) or not schema['minLength'] <= len(value) <= schema['maxLength']:
        raise ValueError('curriculum payload does not match its declared string bounds')
