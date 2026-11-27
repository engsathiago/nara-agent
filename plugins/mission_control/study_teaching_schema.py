"""Optional source-reference teaching contracts; facts still require a domain oracle."""


INSTRUCTION = (
    " The brief declares source-span teaching: select explanation_source_span_id from the supplied source IDs "
    "instead of composing an explanation. The runtime will quote that span exactly. Select question wording "
    "from teaching_schema.questions; derive each answer from its cited source. Do not invent source IDs. "
    "Use an empty explanation_source_span_id only when declining the source."
)


def teaching_schema(brief):
    if 'teaching_schema' not in brief:
        return None
    contract = brief['teaching_schema']
    if (not isinstance(contract, dict) or set(contract) != {'mode', 'questions'}
            or contract['mode'] != 'source-span-v1'):
        raise ValueError('curriculum teaching schema must declare source-span-v1 and questions')
    questions = contract['questions']
    if (not isinstance(questions, list) or not 1 <= len(questions) <= 5
            or any(not isinstance(q, str) or not q.strip() or len(q) > 2000 for q in questions)
            or len(set(questions)) != len(questions)):
        raise ValueError('curriculum teaching schema requires 1-5 distinct bounded questions')
    return contract


def apply_schema(schema, spans, contract):
    if contract is None:
        return schema
    properties = schema['properties']
    properties.pop('explanation')
    properties['explanation_source_span_id'] = {'type': 'string', 'enum': ['', *[
        span['id'] for span in spans if span['text'].strip() and len(span['text']) <= 4000]]}
    properties['questions']['items']['properties']['question'] = {'type': 'string', 'enum': contract['questions']}
    schema['required'] = ['explanation_source_span_id' if key == 'explanation' else key for key in schema['required']]
    return schema


def resolve_teaching(parsed, spans, contract):
    if contract is None:
        return parsed
    expected = {'explanation_source_span_id', 'questions', 'cases', 'decline_reason'}
    if not isinstance(parsed, dict) or set(parsed) != expected:
        raise ValueError('curriculum teaching requires a source span reference, questions, cases and decline_reason')
    normalized = {key: value for key, value in parsed.items() if key != 'explanation_source_span_id'}
    reason = parsed['decline_reason']
    if isinstance(reason, str) and reason.strip():
        return {**normalized, 'explanation': ''}
    identity = parsed['explanation_source_span_id']
    by_id = {span['id']: span for span in spans}
    if not isinstance(identity, str) or identity not in by_id:
        raise ValueError('curriculum explanation must select a supplied source span')
    text = by_id[identity]['text']
    if not text.strip() or len(text) > 4000:
        raise ValueError('curriculum explanation source span exceeds the teaching bounds')
    questions = parsed['questions']
    if not isinstance(questions, list) or any(
            not isinstance(q, dict) or q.get('question') not in contract['questions'] for q in questions):
        raise ValueError('curriculum question is outside its frozen teaching schema')
    return {**normalized, 'explanation': text}
