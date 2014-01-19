import itertools

from jedi import common
from jedi import debug
from jedi import settings
from jedi._compatibility import use_metaclass, is_py3, unicode
from jedi.parser import representation as pr
from jedi.evaluate import compiled
from jedi.evaluate import helpers
from jedi.evaluate.cache import CachedMetaClass, memoize_default


class Generator(use_metaclass(CachedMetaClass, pr.Base)):
    """ Cares for `yield` statements. """
    def __init__(self, evaluator, func, var_args):
        super(Generator, self).__init__()
        self._evaluator = evaluator
        self.func = func
        self.var_args = var_args

    def get_defined_names(self):
        """
        Returns a list of names that define a generator, which can return the
        content of a generator.
        """
        names = []
        executes_generator = ('__next__', 'send')
        for n in ('close', 'throw') + executes_generator:
            parent = self if n in executes_generator else compiled.builtin
            names.append(helpers.FakeName(n, parent))
        debug.dbg('generator names: %s', names)
        return names

    def iter_content(self):
        """ returns the content of __iter__ """
        return self._evaluator.execute(self.func, self.var_args, True)

    def get_index_types(self, index=None):
        debug.warning('Tried to get array access on a generator: %s', self)
        return []

    def __getattr__(self, name):
        if name not in ['start_pos', 'end_pos', 'parent', 'get_imports',
                        'asserts', 'doc', 'docstr', 'get_parent_until',
                        'get_code', 'subscopes']:
            raise AttributeError("Accessing %s of %s is not allowed."
                                 % (self, name))
        return getattr(self.func, name)

    def __repr__(self):
        return "<%s of %s>" % (type(self).__name__, self.func)


class Array(use_metaclass(CachedMetaClass, pr.Base)):
    """
    Used as a mirror to pr.Array, if needed. It defines some getter
    methods which are important in this module.
    """
    def __init__(self, evaluator, array):
        self._evaluator = evaluator
        self._array = array

    def get_index_types(self, index_arr=None):
        """ Get the types of a specific index or all, if not given """
        if index_arr is not None:
            if index_arr and [x for x in index_arr if ':' in x.expression_list()]:
                # array slicing
                return [self]

            index_possibilities = self._follow_values(index_arr)
            if len(index_possibilities) == 1:
                # This is indexing only one element, with a fixed index number,
                # otherwise it just ignores the index (e.g. [1+1]).
                index = index_possibilities[0]
                if isinstance(index, compiled.CompiledObject) \
                        and isinstance(index.obj, (int, str, unicode)):
                    with common.ignored(KeyError, IndexError, TypeError):
                        return self.get_exact_index_types(index.obj)

        result = list(self._follow_values(self._array.values))
        result += check_array_additions(self._evaluator, self)
        return set(result)

    def get_exact_index_types(self, mixed_index):
        """ Here the index is an int/str. Raises IndexError/KeyError """
        index = mixed_index
        if self.type == pr.Array.DICT:
            index = None
            for i, key_statement in enumerate(self._array.keys):
                # Because we only want the key to be a string.
                key_expression_list = key_statement.expression_list()
                if len(key_expression_list) != 1:  # cannot deal with complex strings
                    continue
                key = key_expression_list[0]
                if isinstance(key, pr.Literal):
                    key = key.value
                elif isinstance(key, pr.Name):
                    key = str(key)
                else:
                    continue

                if mixed_index == key:
                    index = i
                    break
            if index is None:
                raise KeyError('No key found in dictionary')

        # Can raise an IndexError
        values = [self._array.values[index]]
        return self._follow_values(values)

    def _follow_values(self, values):
        """ helper function for the index getters """
        return list(itertools.chain.from_iterable(self._evaluator.eval_statement(v)
                                                  for v in values))

    def get_defined_names(self):
        """
        This method generates all `ArrayMethod` for one pr.Array.
        It returns e.g. for a list: append, pop, ...
        """
        # `array.type` is a string with the type, e.g. 'list'.
        scope = self._evaluator.find_types(compiled.builtin, self._array.type)[0]
        scope = self._evaluator.execute(scope)[0]  # builtins only have one class
        names = scope.get_defined_names()
        return [ArrayMethod(n) for n in names]

    @common.safe_property
    def parent(self):
        return compiled.builtin

    def get_parent_until(self):
        return compiled.builtin

    def __getattr__(self, name):
        if name not in ['type', 'start_pos', 'get_only_subelement', 'parent',
                        'get_parent_until', 'items']:
            raise AttributeError('Strange access on %s: %s.' % (self, name))
        return getattr(self._array, name)

    def __getitem__(self):
        return self._array.__getitem__()

    def __iter__(self):
        return self._array.__iter__()

    def __len__(self):
        return self._array.__len__()

    def __repr__(self):
        return "<e%s of %s>" % (type(self).__name__, self._array)


class ArrayMethod(object):
    """
    A name, e.g. `list.append`, it is used to access the original array
    methods.
    """
    def __init__(self, name):
        super(ArrayMethod, self).__init__()
        self.name = name

    def __getattr__(self, name):
        # Set access privileges:
        if name not in ['parent', 'names', 'start_pos', 'end_pos', 'get_code']:
            raise AttributeError('Strange accesson %s: %s.' % (self, name))
        return getattr(self.name, name)

    def get_parent_until(self):
        return compiled.builtin

    def __repr__(self):
        return "<%s of %s>" % (type(self).__name__, self.name)


def get_iterator_types(inputs):
    """Returns the types of any iterator (arrays, yields, __iter__, etc)."""
    iterators = []
    # Take the first statement (for has always only
    # one, remember `in`). And follow it.
    for it in inputs:
        if isinstance(it, (Generator, Array, ArrayInstance)):
            iterators.append(it)
        else:
            if not hasattr(it, 'execute_subscope_by_name'):
                debug.warning('iterator/for loop input wrong: %s', it)
                continue
            try:
                iterators += it.execute_subscope_by_name('__iter__')
            except KeyError:
                debug.warning('iterators: No __iter__ method found.')

    result = []
    from jedi.evaluate.representation import Instance
    for gen in iterators:
        if isinstance(gen, Array):
            # Array is a little bit special, since this is an internal
            # array, but there's also the list builtin, which is
            # another thing.
            result += gen.get_index_types()
        elif isinstance(gen, Instance):
            # __iter__ returned an instance.
            name = '__next__' if is_py3 else 'next'
            try:
                result += gen.execute_subscope_by_name(name)
            except KeyError:
                debug.warning('Instance has no __next__ function in %s.', gen)
        else:
            # is a generator
            result += gen.iter_content()
    return result


def check_array_additions(evaluator, array):
    """ Just a mapper function for the internal _check_array_additions """
    if not pr.Array.is_type(array._array, pr.Array.LIST, pr.Array.SET):
        # TODO also check for dict updates
        return []

    is_list = array._array.type == 'list'
    current_module = array._array.get_parent_until()
    res = _check_array_additions(evaluator, array, current_module, is_list)
    return res


@memoize_default([], evaluator_is_first_arg=True)
def _check_array_additions(evaluator, compare_array, module, is_list):
    """
    Checks if a `pr.Array` has "add" statements:
    >>> a = [""]
    >>> a.append(1)
    """
    if not settings.dynamic_array_additions or isinstance(module, compiled.CompiledObject):
        return []

    def check_calls(calls, add_name):
        """
        Calls are processed here. The part before the call is searched and
        compared with the original Array.
        """
        result = []
        for c in calls:
            call_path = list(c.generate_call_path())
            separate_index = call_path.index(add_name)
            if add_name == call_path[-1] or separate_index == 0:
                # this means that there is no execution -> [].append
                # or the keyword is at the start -> append()
                continue
            backtrack_path = iter(call_path[:separate_index])

            position = c.start_pos
            scope = c.get_parent_until(pr.IsScope)

            found = evaluator.eval_call_path(backtrack_path, scope, position)
            if not compare_array in found:
                continue

            params = call_path[separate_index + 1]
            if not params.values:
                continue  # no params: just ignore it
            if add_name in ['append', 'add']:
                for param in params:
                    result += evaluator.eval_statement(param)
            elif add_name in ['insert']:
                try:
                    second_param = params[1]
                except IndexError:
                    continue
                else:
                    result += evaluator.eval_statement(second_param)
            elif add_name in ['extend', 'update']:
                for param in params:
                    iterators = evaluator.eval_statement(param)
                result += get_iterator_types(iterators)
        return result

    from jedi.evaluate import representation as er

    def get_execution_parent(element, *stop_classes):
        """ Used to get an Instance/FunctionExecution parent """
        if isinstance(element, Array):
            stmt = element._array.parent
        else:
            # is an Instance with an ArrayInstance inside
            stmt = element.var_args[0].var_args.parent
        if isinstance(stmt, er.InstanceElement):
            stop_classes = list(stop_classes) + [er.Function]
        return stmt.get_parent_until(stop_classes)

    temp_param_add = settings.dynamic_params_for_other_modules
    settings.dynamic_params_for_other_modules = False

    search_names = ['append', 'extend', 'insert'] if is_list else \
        ['add', 'update']
    comp_arr_parent = get_execution_parent(compare_array, er.FunctionExecution)

    possible_stmts = []
    res = []
    for n in search_names:
        try:
            possible_stmts += module.used_names[n]
        except KeyError:
            continue
        for stmt in possible_stmts:
            # Check if the original scope is an execution. If it is, one
            # can search for the same statement, that is in the module
            # dict. Executions are somewhat special in jedi, since they
            # literally copy the contents of a function.
            if isinstance(comp_arr_parent, er.FunctionExecution):
                stmt = comp_arr_parent. \
                    get_statement_for_position(stmt.start_pos)
                if stmt is None:
                    continue
            # InstanceElements are special, because they don't get copied,
            # but have this wrapper around them.
            if isinstance(comp_arr_parent, er.InstanceElement):
                stmt = er.InstanceElement(comp_arr_parent.instance, stmt)

            if evaluator.recursion_detector.push_stmt(stmt):
                # check recursion
                continue

            res += check_calls(helpers.scan_statement_for_calls(stmt, n), n)
            evaluator.recursion_detector.pop_stmt()
    # reset settings
    settings.dynamic_params_for_other_modules = temp_param_add
    return res


def check_array_instances(evaluator, instance):
    """Used for set() and list() instances."""
    if not settings.dynamic_arrays_instances:
        return instance.var_args
    ai = ArrayInstance(evaluator, instance)
    return [ai]


class ArrayInstance(pr.Base):
    """
    Used for the usage of set() and list().
    This is definitely a hack, but a good one :-)
    It makes it possible to use set/list conversions.
    """
    def __init__(self, evaluator, instance):
        self._evaluator = evaluator
        self.instance = instance
        self.var_args = instance.var_args

    def iter_content(self):
        """
        The index is here just ignored, because of all the appends, etc.
        lists/sets are too complicated too handle that.
        """
        items = []
        from jedi.evaluate.representation import Instance
        for stmt in self.var_args:
            for typ in self._evaluator.eval_statement(stmt):
                if isinstance(typ, Instance) and len(typ.var_args):
                    array = typ.var_args[0]
                    if isinstance(array, ArrayInstance):
                        # prevent recursions
                        # TODO compare Modules
                        if self.var_args.start_pos != array.var_args.start_pos:
                            items += array.iter_content()
                        else:
                            debug.warning('ArrayInstance recursion %s', self.var_args)
                        continue
                items += get_iterator_types([typ])

        # TODO check if exclusion of tuple is a problem here.
        if isinstance(self.var_args, tuple) or self.var_args.parent is None:
            return []  # generated var_args should not be checked for arrays

        module = self.var_args.get_parent_until()
        is_list = str(self.instance.name) == 'list'
        items += _check_array_additions(self._evaluator, self.instance, module, is_list)
        return items
