"""
Implementations of standard library functions, because it's not possible to
understand them with Jedi.
"""

from jedi._compatibility import unicode
from jedi.evaluate import compiled
from jedi.evaluate import representation as er
from jedi.evaluate import iterable
from jedi.parser import representation as pr
from jedi import debug


class NotInStdLib(LookupError):
    pass


def execute(evaluator, obj, params):
    if not isinstance(obj, (iterable.Generator, iterable.Array)):
        obj_name = str(obj.name)
        if obj.parent == compiled.builtin:
            # for now we just support builtin functions.
            try:
                return _implemented['builtins'][obj_name](evaluator, obj, params)
            except KeyError:
                pass
    raise NotInStdLib()


def _follow_param(evaluator, params, index):
    try:
        stmt = params[index]
    except IndexError:
        return []
    else:
        if isinstance(stmt, pr.Statement):
            return evaluator.eval_statement(stmt)
        else:
            return [stmt]  # just some arbitrary object


def builtins_getattr(evaluator, obj, params):
    stmts = []
    # follow the first param
    objects = _follow_param(evaluator, params, 0)
    names = _follow_param(evaluator, params, 1)
    for obj in objects:
        if not isinstance(obj, (er.Instance, er.Class, pr.Module, compiled.CompiledObject)):
            debug.warning('getattr called without instance')
            continue

        for name in names:
            s = unicode, str
            if isinstance(name, compiled.CompiledObject) and isinstance(name.obj, s):
                stmts += evaluator.follow_path(iter([name.obj]), [obj], obj)
            else:
                debug.warning('getattr called without str')
                continue
    return stmts


def builtins_type(evaluator, obj, params):
    if len(params) == 1:
        # otherwise it would be a metaclass... maybe someday...
        objects = _follow_param(evaluator, params, 0)
        return [o.base for o in objects if isinstance(o, er.Instance)]
    return []


def builtins_super(evaluator, obj, params):
    # TODO make this able to detect multiple inheritance super
    accept = (pr.Function,)
    func = params.get_parent_until(accept)
    if func.isinstance(*accept):
        cls = func.get_parent_until(accept + (pr.Class,),
                                    include_current=False)
        if isinstance(cls, pr.Class):
            cls = er.Class(evaluator, cls)
            su = cls.get_super_classes()
            if su:
                return evaluator.execute(su[0])
    return []


_implemented = {
    'builtins': {
        'getattr': builtins_getattr,
        'type': builtins_type,
        'super': builtins_super,
    }
}
