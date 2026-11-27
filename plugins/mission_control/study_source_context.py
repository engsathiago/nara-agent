"""Versioned, deterministic source views; never rewrite archived text or citation IDs."""

from collections import Counter
from fractions import Fraction
import re

from plugins.mission_control.learning_study_sources import source_spans


CONTEXT_INSTRUCTION = (" Source context is a bounded lexical selection of original spans, not a complete page. "
                       "Omitted text is unknown; absence from this view is not proof that a claim is absent from the source.")


STOP_WORDS = frozenset('a an and are as at be by de do e em for from in is it of on or os para que the to um uma use with'.split())


def validate_source_context(spec):
    if spec is None:
        return None
    if (not isinstance(spec, dict) or set(spec) - {'strategy', 'max_characters', 'terms'}
            or spec.get('strategy') != 'lexical-spans-v1'):
        raise ValueError('source context requires the lexical-spans-v1 strategy')
    budget = spec.get('max_characters')
    if type(budget) is not int or not 2000 <= budget <= 24000:
        raise ValueError('source context max_characters must be an integer from 2000 to 24000')
    terms = spec.get('terms', [])
    if (not isinstance(terms, list) or len(terms) > 12
            or any(not isinstance(term, str) or not term.strip() or len(term) > 64 for term in terms)):
        raise ValueError('source context terms must contain at most 12 bounded public topic terms')
    return {'strategy': 'lexical-spans-v1', 'max_characters': budget,
            'terms': sorted({term.strip().casefold() for term in terms})}


def _tokens(text):
    return {term for term in re.findall(r'\w+', text.casefold()) if len(term) > 1 and term not in STOP_WORDS}


def project_source(text, objective, spec):
    spec = validate_source_context(spec)
    spans = source_spans(text)
    if spec is None:
        return spans, None  # Frozen v1-v4 inputs must retain their original exact shape.
    topics = _tokens(' '.join(spec['terms']))
    query = _tokens(objective) | topics
    words = [_tokens(span['text']) for span in spans]
    frequencies = Counter(term for tokens in words for term in tokens & query)
    def rank(index):
        matches = words[index] & query
        relevance = sum((Fraction(1, frequencies[term]) for term in sorted(matches)), Fraction(0))
        return (-len(words[index] & topics), -relevance, spans[index]['start'])
    used, selected = 0, []
    for index in sorted(range(len(spans)), key=rank):
        span = spans[index]
        if used + len(span['text']) <= spec['max_characters']:
            selected.append(span)
            used += len(span['text'])
    selected.sort(key=lambda span: span['start'])
    return selected, {**spec, 'source_characters': len(text), 'selected_characters': used,
                      'omitted_spans': len(spans) - len(selected),
                      'coverage': 'partial' if len(selected) < len(spans) else 'all_spans'}
