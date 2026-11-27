"""Apply verified category measurements at the existing core child-creation seam."""

import copy
import re

from agent.delegation_provider import DelegationProvider, DelegationRouteError, ROUTE_KEYS
from plugins.mission_control.specialists import ModelCandidate, ModelCapabilityRegistry


_CAPABILITIES = {'supports_tools', 'supports_vision', 'supports_reasoning', 'context_window'}


def _candidate(route):
    for name in ('provider', 'model'):
        value = route.get(name)
        if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 200:
            raise DelegationRouteError(f'nara-measured routes require a nonempty {name}')
    capabilities = route.get('capabilities', {})
    if not isinstance(capabilities, dict) or set(capabilities) - _CAPABILITIES:
        raise DelegationRouteError('nara-measured capabilities contain unsupported fields')
    for name in ('supports_tools', 'supports_vision', 'supports_reasoning'):
        if capabilities.get(name) is not None and type(capabilities[name]) is not bool:
            raise DelegationRouteError(f'nara-measured capability {name} must be boolean or null')
    context = capabilities.get('context_window', 0)
    if type(context) is not int or not 0 <= context <= 8_000_000:
        raise DelegationRouteError('nara-measured context_window must be a nonnegative integer up to 8000000')
    return ModelCandidate(route['provider'], route['model'], capabilities.get('supports_tools') is True,
                          capabilities.get('supports_vision'), capabilities.get('supports_reasoning'), context)


def _pool(settings):
    routes = settings.get('routes')
    if not isinstance(routes, list) or not 1 <= len(routes) <= 32:
        raise DelegationRouteError('Configure 1-32 routes in delegation.backends.nara-measured.routes')
    candidates, indexed = [], {}
    for route in routes:
        if not isinstance(route, dict) or set(route) - ((ROUTE_KEYS - {'profile', 'label'}) | {'capabilities'}):
            raise DelegationRouteError('nara-measured route fields are invalid; profile routes are not supported')
        candidate = _candidate(route)
        key = (candidate.provider, candidate.model)
        if key in indexed:
            raise DelegationRouteError('nara-measured routes must have distinct provider/model identities')
        indexed[key] = {key: copy.deepcopy(value) for key, value in route.items() if key in ROUTE_KEYS}
        candidates.append(candidate)
    return ModelCapabilityRegistry(candidates), indexed


def _requirements(task):
    category = task.get('task_category')
    if category is not None and (not isinstance(category, str) or not re.fullmatch(r'[a-z][a-z0-9_.-]{0,119}', category)):
        raise DelegationRouteError('task_category must be an exact lowercase benchmark category')
    scope = task.get('benchmark_scope')
    if scope is not None and (category is None or not isinstance(scope, str) or not re.fullmatch(r'[0-9a-f]{64}', scope)):
        raise DelegationRouteError('benchmark_scope requires a task_category and its 64-character cohort hash')
    vision = task.get('requires_vision', False)
    context = task.get('min_context', 0)
    if type(vision) is not bool or type(context) is not int or not 0 <= context <= 8_000_000:
        raise DelegationRouteError('requires_vision must be boolean and min_context a nonnegative bounded integer')
    return {'requires_tools': True, 'requires_vision': vision, 'min_context': context,
            'category': category, 'benchmark_scope': scope}


class MeasuredDelegationProvider(DelegationProvider):
    @property
    def name(self):
        return 'nara-measured'

    @property
    def display_name(self):
        return 'Nara measured routing'

    @property
    def summary(self):
        return 'Choose each child model from configured routes using verified category results.'

    def task_parameters(self, config):
        # Measurement history never changes the cached tool schema within a session.
        return {
            'task_category': {'type': 'string', 'description': 'Exact benchmark category; omit when unknown.'},
            'benchmark_scope': {'type': 'string', 'description': 'Optional exact frozen benchmark cohort hash.'},
            'requires_vision': {'type': 'boolean', 'description': 'Whether this task requires a vision model.'},
            'min_context': {'type': 'integer', 'minimum': 0, 'maximum': 8_000_000,
                            'description': 'Minimum required model context capacity.'},
        }

    def description(self, config):
        return ('Nara chooses a configured model for each new child using verified task-category measurements. '
                'Supply task_category only when known, plus vision/context requirements. '
                'Without comparable measurements, selection uses configured capabilities. '
                'This does not change the model of an already running child.')

    def route_task(self, task, config):
        registry, routes = _pool(self.settings(config))
        requirements = _requirements(task)
        selected = registry.select(**requirements)
        if selected is None:
            raise DelegationRouteError('No configured nara-measured route satisfies this task; revise requirements or routes')
        route = routes[(selected.provider, selected.model)]
        performance = selected.performance
        if performance:
            route['label'] = (f"{selected.model}: {performance['success_rate']:.1%} verified in "
                              f"{performance['category']} ({performance['sample_count']} samples; "
                              f"cohort {performance['benchmark_scope']})")
        else:
            route['label'] = f'{selected.model}: configured capabilities; no comparable category measurement'
        return route
