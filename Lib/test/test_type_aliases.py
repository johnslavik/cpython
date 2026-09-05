import ast
import pickle
import types
import unittest
import weakref
from test.support import check_syntax_error, gc_collect, run_code
from test.support import os_helper, script_helper
from test.typinganndata import mod_generics_cache

from typing import (
    Callable, TypeAliasType, TypeVar, TypeVarTuple, ParamSpec, Unpack, get_args,
)

type GlobalTypeAlias = int
type DocumentedGlobalTypeAlias = int
"""A module-scoped alias."""

def get_type_alias():
    type TypeAliasInFunc = str
    return TypeAliasInFunc

class TypeParamsInvalidTest(unittest.TestCase):
    def test_name_collisions(self):
        check_syntax_error(self, 'type TA1[A, **A] = None', "duplicate type parameter 'A'")
        check_syntax_error(self, 'type T[A, *A] = None', "duplicate type parameter 'A'")
        check_syntax_error(self, 'type T[*A, **A] = None', "duplicate type parameter 'A'")

    def test_name_non_collision_02(self):
        ns = run_code("""type TA1[A] = lambda A: A""")
        self.assertIsInstance(ns["TA1"], TypeAliasType)
        self.assertTrue(callable(ns["TA1"].__value__))
        self.assertEqual("arg", ns["TA1"].__value__("arg"))

    def test_name_non_collision_03(self):
        ns = run_code("""
            class Outer[A]:
                type TA1[A] = None
            """
        )
        outer_A, = ns["Outer"].__type_params__
        inner_A, = ns["Outer"].TA1.__type_params__
        self.assertIsNot(outer_A, inner_A)


class TypeParamsAccessTest(unittest.TestCase):
    def test_alias_access_01(self):
        ns = run_code("type TA1[A, B] = dict[A, B]")
        alias = ns["TA1"]
        self.assertIsInstance(alias, TypeAliasType)
        self.assertEqual(alias.__type_params__, get_args(alias.__value__))

    def test_alias_access_02(self):
        ns = run_code("""
            type TA1[A, B] = TA1[A, B] | int
            """
        )
        alias = ns["TA1"]
        self.assertIsInstance(alias, TypeAliasType)
        A, B = alias.__type_params__
        self.assertEqual(alias.__value__, alias[A, B] | int)

    def test_alias_access_03(self):
        ns = run_code("""
            class Outer[A]:
                def inner[B](self):
                    type TA1[C] = TA1[A, B] | int
                    return TA1
            """
        )
        cls = ns["Outer"]
        A, = cls.__type_params__
        B, = cls.inner.__type_params__
        alias = cls.inner(None)
        self.assertIsInstance(alias, TypeAliasType)
        alias2 = cls.inner(None)
        self.assertIsNot(alias, alias2)
        self.assertEqual(len(alias.__type_params__), 1)

        self.assertEqual(alias.__value__, alias[A, B] | int)


class TypeParamsAliasValueTest(unittest.TestCase):
    type TypeAliasInClass = dict

    def test_alias_value_01(self):
        type TA1 = int

        self.assertIsInstance(TA1, TypeAliasType)
        self.assertEqual(TA1.__value__, int)
        self.assertEqual(TA1.__parameters__, ())
        self.assertEqual(TA1.__type_params__, ())

        type TA2 = TA1 | str

        self.assertIsInstance(TA2, TypeAliasType)
        a, b = TA2.__value__.__args__
        self.assertEqual(a, TA1)
        self.assertEqual(b, str)
        self.assertEqual(TA2.__parameters__, ())
        self.assertEqual(TA2.__type_params__, ())

    def test_alias_value_02(self):
        class Parent[A]:
            type TA1[B] = dict[A, B]

        self.assertIsInstance(Parent.TA1, TypeAliasType)
        self.assertEqual(len(Parent.TA1.__parameters__), 1)
        self.assertEqual(len(Parent.__parameters__), 1)
        a, = Parent.__parameters__
        b, = Parent.TA1.__parameters__
        self.assertEqual(Parent.__type_params__, (a,))
        self.assertEqual(Parent.TA1.__type_params__, (b,))
        self.assertEqual(Parent.TA1.__value__, dict[a, b])

    def test_alias_value_03(self):
        def outer[A]():
            type TA1[B] = dict[A, B]
            return TA1

        o = outer()
        self.assertIsInstance(o, TypeAliasType)
        self.assertEqual(len(o.__parameters__), 1)
        self.assertEqual(len(outer.__type_params__), 1)
        b = o.__parameters__[0]
        self.assertEqual(o.__type_params__, (b,))

    def test_alias_value_04(self):
        def more_generic[T, *Ts, **P]():
            type TA[T2, *Ts2, **P2] = tuple[Callable[P, tuple[T, *Ts]], Callable[P2, tuple[T2, *Ts2]]]
            return TA

        alias = more_generic()
        self.assertIsInstance(alias, TypeAliasType)
        T2, Ts2, P2 = alias.__type_params__
        self.assertEqual(alias.__parameters__, (T2, *Ts2, P2))
        T, Ts, P = more_generic.__type_params__
        self.assertEqual(alias.__value__, tuple[Callable[P, tuple[T, *Ts]], Callable[P2, tuple[T2, *Ts2]]])

    def test_subscripting(self):
        type NonGeneric = int
        type Generic[A] = dict[A, A]
        type VeryGeneric[T, *Ts, **P] = Callable[P, tuple[T, *Ts]]

        with self.assertRaises(TypeError):
            NonGeneric[int]

        specialized = Generic[int]
        self.assertIsInstance(specialized, types.GenericAlias)
        self.assertIs(specialized.__origin__, Generic)
        self.assertEqual(specialized.__args__, (int,))

        specialized2 = VeryGeneric[int, str, float, [bool, range]]
        self.assertIsInstance(specialized2, types.GenericAlias)
        self.assertIs(specialized2.__origin__, VeryGeneric)
        self.assertEqual(specialized2.__args__, (int, str, float, [bool, range]))

    def test___name__(self):
        type TypeAliasLocal = GlobalTypeAlias

        self.assertEqual(GlobalTypeAlias.__name__, 'GlobalTypeAlias')
        self.assertEqual(get_type_alias().__name__, 'TypeAliasInFunc')
        self.assertEqual(self.TypeAliasInClass.__name__, 'TypeAliasInClass')
        self.assertEqual(TypeAliasLocal.__name__, 'TypeAliasLocal')

        with self.assertRaisesRegex(
            AttributeError,
            "readonly attribute",
        ):
            setattr(TypeAliasLocal, '__name__', 'TA')

    def test___qualname__(self):
        type TypeAliasLocal = GlobalTypeAlias

        self.assertEqual(GlobalTypeAlias.__qualname__,
                         'GlobalTypeAlias')
        self.assertEqual(get_type_alias().__qualname__,
                         'get_type_alias.<locals>.TypeAliasInFunc')
        self.assertEqual(self.TypeAliasInClass.__qualname__,
                         'TypeParamsAliasValueTest.TypeAliasInClass')
        self.assertEqual(TypeAliasLocal.__qualname__,
                         'TypeParamsAliasValueTest.test___qualname__.<locals>.TypeAliasLocal')

        with self.assertRaisesRegex(
            AttributeError,
            "readonly attribute",
        ):
            setattr(TypeAliasLocal, '__qualname__', 'TA')

    def test___doc__(self):
        type Undocumented = int
        type Documented[T] = list[T]
        """A documented generic type alias."""

        self.assertIsNone(Undocumented.__doc__)
        self.assertEqual(Documented.__doc__,
                         "A documented generic type alias.")
        self.assertEqual(DocumentedGlobalTypeAlias.__doc__,
                         "A module-scoped alias.")

    def test_docstring_scopes(self):
        class Container:
            type Alias = int
            """A class-scoped alias."""

        def make_alias():
            type Alias = str
            """A function-scoped alias.

            More details.
            """
            return Alias

        self.assertEqual(Container.Alias.__doc__,
                         "A class-scoped alias.")
        self.assertEqual(make_alias().__doc__,
                         "A function-scoped alias.\n\nMore details.\n")

    def test_docstring_nested_suites(self):
        docs = []

        if True:
            type InIf = int
            """In an if body."""
            docs.append(InIf.__doc__)
        if False:
            pass
        else:
            type InElse = int
            """In an else body."""
            docs.append(InElse.__doc__)

        for _ in (None,):
            type InFor = int
            """In a for body."""
            docs.append(InFor.__doc__)
        else:
            type InForElse = int
            """In a for else body."""
            docs.append(InForElse.__doc__)

        while True:
            type InWhile = int
            """In a while body."""
            docs.append(InWhile.__doc__)
            break
        while False:
            pass
        else:
            type InWhileElse = int
            """In a while else body."""
            docs.append(InWhileElse.__doc__)

        with self.subTest(suite="with"):
            type InWith = int
            """In a with body."""
            docs.append(InWith.__doc__)

        try:
            type InTry = int
            """In a try body."""
            docs.append(InTry.__doc__)
        except Exception:
            self.fail("unexpected exception")
        else:
            type InTryElse = int
            """In a try else body."""
            docs.append(InTryElse.__doc__)
        finally:
            type InFinally = int
            """In a finally body."""
            docs.append(InFinally.__doc__)

        try:
            raise ValueError
        except ValueError:
            type InExcept = int
            """In an except body."""
            docs.append(InExcept.__doc__)

        try:
            raise ExceptionGroup("test", [ValueError()])
        except* ValueError:
            type InExceptStar = int
            """In an except-star body."""
            docs.append(InExceptStar.__doc__)

        match None:
            case None:
                type InMatch = int
                """In a match case."""
                docs.append(InMatch.__doc__)

        self.assertEqual(docs, [
            "In an if body.",
            "In an else body.",
            "In a for body.",
            "In a for else body.",
            "In a while body.",
            "In a while else body.",
            "In a with body.",
            "In a try body.",
            "In a try else body.",
            "In a finally body.",
            "In an except body.",
            "In an except-star body.",
            "In a match case.",
        ])

    def test_docstring_async_suites(self):
        class AsyncIterator:
            def __init__(self):
                self.done = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.done:
                    raise StopAsyncIteration
                self.done = True
                return None

        class AsyncContextManager:
            async def __aenter__(self):
                return None

            async def __aexit__(self, *exc_info):
                pass

        async def nested():
            docs = []
            async for _ in AsyncIterator():
                type InAsyncFor = int
                """In an async for body."""
                docs.append(InAsyncFor.__doc__)
            else:
                type InAsyncForElse = int
                """In an async for else body."""
                docs.append(InAsyncForElse.__doc__)

            async with AsyncContextManager():
                type InAsyncWith = int
                """In an async with body."""
                docs.append(InAsyncWith.__doc__)
            return docs

        with self.assertRaises(StopIteration) as caught:
            nested().send(None)
        self.assertEqual(caught.exception.value, [
            "In an async for body.",
            "In an async for else body.",
            "In an async with body.",
        ])

    def test_docstring_attachment(self):
        type First = int
        """The first alias."""
        type Second = str
        """The second alias."""
        type NonString = bytes
        42
        type InterveningStatement = float
        marker = None
        """Not an alias docstring."""

        self.assertEqual(First.__doc__, "The first alias.")
        self.assertEqual(Second.__doc__, "The second alias.")
        self.assertIsNone(NonString.__doc__)
        self.assertIsNone(InterveningStatement.__doc__)
        self.assertIsNone(marker)

    def test_docstring_optimization(self):
        code = compile(
            'type First = int\n'
            '"""The first alias."""\n'
            'type Second[T] = list[T]\n'
            '"""The second alias."""\n'
            'if True:\n'
            '    type Nested = bytes\n'
            '    """The nested alias."""\n'
            'marker = True\n',
            "<test>", "exec", optimize=2,
        )
        ns = {}
        exec(code, ns)

        self.assertIsNone(ns["First"].__doc__)
        self.assertIsNone(ns["Second"].__doc__)
        self.assertIsNone(ns["Nested"].__doc__)
        self.assertIs(ns["marker"], True)

    def test_additional_docstrings_and_folded_expressions(self):
        expressions = (
            ('"primary"\n"additional"', "primary"),
            ('"primary"\n"additional"\n"third"', "primary"),
            ('"not " + "documentation"', None),
            ('"not documentation" * 2', None),
            ('f"not documentation"', None),
        )
        for expression, doc in expressions:
            for optimize in (0, 1, 2):
                for nested in (False, True):
                    with self.subTest(expression=expression,
                                      optimize=optimize, nested=nested):
                        source = "type Alias = int\n" + expression + "\n"
                        if nested:
                            source = "if True:\n" + "".join(
                                "    " + line + "\n"
                                for line in source.splitlines()
                            )
                        source += 'type Next = str\n"next doc"\nmarker = True\n'
                        ns = {}
                        exec(compile(source, "<test>", "exec",
                                     optimize=optimize), ns)
                        self.assertEqual(ns["Alias"].__doc__,
                                         doc if optimize < 2 else None)
                        self.assertEqual(ns["Next"].__doc__,
                                         "next doc" if optimize < 2 else None)
                        self.assertTrue(ns["marker"])

    def test_docstring_stripped_from_ast(self):
        source = 'type Alias = int\n"primary"\n"additional"\n'
        tree = compile(source, "<test>", "exec", ast.PyCF_ONLY_AST,
                       optimize=2)
        self.assertFalse(any(
            isinstance(node, ast.Constant) and node.value == "primary"
            for node in ast.walk(tree)
        ))
        self.assertIsNone(tree.body[0].doc)
        self.assertIsNone(ast.get_docstring(tree.body[0]))
        self.assertIsInstance(tree.body[1].value, ast.JoinedStr)
        ns = {}
        # Recompiling the stripped tree must not promote the additional string.
        exec(compile(tree, "<test>", "exec", optimize=0), ns)
        self.assertIsNone(ns["Alias"].__doc__)

    def test_docstring_from_file(self):
        source = (
            'type Alias[T] = list[T]\n'
            '"""A type alias.\n\n    More details.\n"""\n'
            'print(repr(Alias.__doc__))\n'
        )
        with os_helper.temp_dir() as temp_dir:
            script = script_helper.make_script(
                temp_dir, "type_alias_doc", source,
            )
            _, stdout, _ = script_helper.assert_python_ok(script)
            self.assertEqual(
                stdout, b"'A type alias.\\n\\nMore details.\\n'\n",
            )

            _, stdout, _ = script_helper.assert_python_ok("-OO", script)
            self.assertEqual(stdout, b"None\n")

    def test_docstring_ast_round_trip(self):
        tree = ast.parse(
            'type Alias[T] = list[T]\n'
            '"""A type alias.\n\n    More details.\n"""\n'
        )
        alias = tree.body[0]
        self.assertEqual(alias._fields, ("name", "type_params", "value", "doc"))
        self.assertEqual(len(tree.body), 2)
        self.assertIsInstance(tree.body[1], ast.Expr)
        self.assertIsInstance(tree.body[1].value, ast.Constant)
        self.assertEqual(tree.body[1].value.value, alias.doc)
        self.assertEqual(alias.doc, "A type alias.\n\n    More details.\n")
        self.assertEqual(ast.get_docstring(alias, clean=False), alias.doc)
        self.assertEqual(ast.get_docstring(alias),
                         "A type alias.\n\nMore details.")
        self.assertEqual(ast.dump(tree).count("A type alias."), 2)
        self.assertEqual(repr(tree).count("A type alias."), 2)
        self.assertTrue(ast.compare(tree, ast.parse(ast.unparse(tree))))

        doc = "A type alias.\n\nMore details.\n"
        levels = ((0, doc), (1, doc), (2, None))
        for optimize, expected in levels:
            with self.subTest(optimize=optimize):
                ns = {}
                code = compile(tree, "<ast>", "exec", optimize=optimize)
                exec(code, ns)
                self.assertEqual(ns["Alias"].__doc__, expected)

    def test_docstring_ast_field(self):
        for doc in (None, "", "  Updated documentation."):
            with self.subTest(doc=doc):
                alias = ast.TypeAlias(
                    ast.Name(id="Alias", ctx=ast.Store()), [],
                    ast.Name(id="int", ctx=ast.Load()),
                )
                self.assertIsNone(alias.doc)
                alias.doc = doc
                tree = ast.fix_missing_locations(ast.Module(body=[alias],
                                                           type_ignores=[]))
                self.assertEqual(ast.get_docstring(alias, clean=False), doc)
                reparsed = ast.parse(ast.unparse(tree))
                self.assertIsNone(reparsed.body[0].doc)
                self.assertEqual(len(reparsed.body), 1)
                ns = {}
                exec(compile(tree, "<ast>", "exec"), ns)
                self.assertEqual(ns["Alias"].__doc__,
                                 None if doc is None else doc.lstrip())

    def test_unparse_uses_docstring_statement(self):
        tree = ast.parse('type Alias = int\n"Original documentation."')
        tree.body[0].doc = "Different field value."
        source = ast.unparse(tree)
        self.assertNotIn("Different field value.", source)
        reparsed = ast.parse(source)
        self.assertEqual(reparsed.body[0].doc, "Original documentation.")
        self.assertEqual(len(reparsed.body), 2)

    def test_docstring_ast_preprocessing(self):
        source = ('if True:\n'
                  '    type Alias = int\n'
                  '    # Documentation may follow comments and blank lines.\n'
                  '\n'
                  '    "primary"\n'
                  '    "additional"\n')
        for optimize in (0, 1, 2):
            with self.subTest(optimize=optimize):
                tree = ast.parse(source, optimize=optimize)
                alias = tree.body[0].body[0]
                self.assertEqual(alias.doc, "primary" if optimize < 2 else None)
                reparsed = ast.parse(ast.unparse(tree))
                self.assertEqual(reparsed.body[0].body[0].doc, alias.doc)
                # Reprocessing the AST must not attach the additional string.
                ns = {}
                exec(compile(tree, "<ast>", "exec"), ns)
                self.assertEqual(ns["Alias"].__doc__, alias.doc)

    def test_repr(self):
        type Simple = int
        self.assertEqual(repr(Simple), Simple.__qualname__)

        type VeryGeneric[T, *Ts, **P] = Callable[P, tuple[T, *Ts]]
        self.assertEqual(repr(VeryGeneric), VeryGeneric.__qualname__)
        fullname = f"{VeryGeneric.__module__}.{VeryGeneric.__qualname__}"
        self.assertEqual(repr(VeryGeneric[int, bytes, str, [float, object]]),
                         f"{fullname}[int, bytes, str, [float, object]]")
        self.assertEqual(repr(VeryGeneric[int, []]),
                         f"{fullname}[int, []]")
        self.assertEqual(repr(VeryGeneric[int, [VeryGeneric[int], list[str]]]),
                         f"{fullname}[int, [{fullname}[int], list[str]]]")

    def test_recursive_repr(self):
        type Recursive = Recursive
        self.assertEqual(repr(Recursive), Recursive.__qualname__)

        type X = list[Y]
        type Y = list[X]
        self.assertEqual(repr(X), X.__qualname__)
        self.assertEqual(repr(Y), Y.__qualname__)

        type GenericRecursive[X] = list[X | GenericRecursive[X]]
        self.assertEqual(repr(GenericRecursive), GenericRecursive.__qualname__)
        fullname = f"{GenericRecursive.__module__}.{GenericRecursive.__qualname__}"
        self.assertEqual(repr(GenericRecursive[int]), f"{fullname}[int]")
        self.assertEqual(repr(GenericRecursive[GenericRecursive[int]]),
                         f"{fullname}[{fullname}[int]]")

    def test_raising(self):
        type MissingName = list[_My_X]
        with self.assertRaisesRegex(
            NameError,
            "cannot access free variable '_My_X' where it is not associated with a value",
        ):
            MissingName.__value__
        _My_X = int
        self.assertEqual(MissingName.__value__, list[int])
        del _My_X
        # Cache should still work:
        self.assertEqual(MissingName.__value__, list[int])

        # Explicit exception:
        type ExprException = 1 / 0
        with self.assertRaises(ZeroDivisionError):
            ExprException.__value__


class TypeAliasConstructorTest(unittest.TestCase):
    def test_basic(self):
        TA = TypeAliasType("TA", int)
        self.assertEqual(TA.__name__, "TA")
        self.assertEqual(TA.__qualname__, "TA")
        self.assertIs(TA.__value__, int)
        self.assertEqual(TA.__type_params__, ())
        self.assertEqual(TA.__module__, __name__)
        self.assertIsNone(TA.__doc__)

    def test_with_qualname(self):
        TA = TypeAliasType("TA", str, qualname="Class.TA")
        self.assertEqual(TA.__name__, "TA")
        self.assertEqual(TA.__qualname__, "Class.TA")
        self.assertIs(TA.__value__, str)
        self.assertEqual(TA.__type_params__, ())
        self.assertEqual(TA.__module__, __name__)

    def test_attributes_with_exec(self):
        ns = {}
        exec("type TA = int", ns, ns)
        TA = ns["TA"]
        self.assertEqual(TA.__name__, "TA")
        self.assertEqual(TA.__qualname__, "TA")
        self.assertIs(TA.__value__, int)
        self.assertEqual(TA.__type_params__, ())
        self.assertIs(TA.__module__, None)

    def test_generic(self):
        T = TypeVar("T")
        TA = TypeAliasType("TA", list[T], type_params=(T,))
        self.assertEqual(TA.__name__, "TA")
        self.assertEqual(TA.__qualname__, "TA")
        self.assertEqual(TA.__value__, list[T])
        self.assertEqual(TA.__type_params__, (T,))
        self.assertEqual(TA.__module__, __name__)
        self.assertIs(type(TA[int]), types.GenericAlias)

    def test_not_generic(self):
        TA = TypeAliasType("TA", list[int], type_params=())
        self.assertEqual(TA.__name__, "TA")
        self.assertEqual(TA.__qualname__, "TA")
        self.assertEqual(TA.__value__, list[int])
        self.assertEqual(TA.__type_params__, ())
        self.assertEqual(TA.__module__, __name__)
        with self.assertRaisesRegex(
            TypeError,
            "Only generic type aliases are subscriptable",
        ):
            TA[int]

    def test_type_params_order_with_defaults(self):
        HasNoDefaultT = TypeVar("HasNoDefaultT")
        WithDefaultT = TypeVar("WithDefaultT", default=int)

        HasNoDefaultP = ParamSpec("HasNoDefaultP")
        WithDefaultP = ParamSpec("WithDefaultP", default=HasNoDefaultP)

        HasNoDefaultTT = TypeVarTuple("HasNoDefaultTT")
        WithDefaultTT = TypeVarTuple("WithDefaultTT", default=HasNoDefaultTT)

        for type_params in [
            (HasNoDefaultT, WithDefaultT),
            (HasNoDefaultP, WithDefaultP),
            (HasNoDefaultTT, WithDefaultTT),
        ]:
            with self.subTest(type_params=type_params):
                TypeAliasType("A", int, type_params=type_params)  # ok

        msg = "follows default type parameter"
        for type_params in [
            (WithDefaultT, HasNoDefaultT),
            (WithDefaultP, HasNoDefaultP),
            (WithDefaultTT, HasNoDefaultTT),
            (WithDefaultT, HasNoDefaultP),  # different types
        ]:
            with self.subTest(type_params=type_params):
                with self.assertRaisesRegex(TypeError, msg):
                    TypeAliasType("A", int, type_params=type_params)

    def test_expects_type_like(self):
        T = TypeVar("T")

        msg = "Expected a type param"
        with self.assertRaisesRegex(TypeError, msg):
            TypeAliasType("A", int, type_params=(1,))
        with self.assertRaisesRegex(TypeError, msg):
            TypeAliasType("A", int, type_params=(1, 2))
        with self.assertRaisesRegex(TypeError, msg):
            TypeAliasType("A", int, type_params=(T, 2))

    def test_keywords(self):
        TA = TypeAliasType(name="TA", value=int, type_params=(), qualname=None)
        self.assertEqual(TA.__name__, "TA")
        self.assertEqual(TA.__qualname__, "TA")
        self.assertIsNone(TA.__doc__)
        self.assertIs(TA.__value__, int)
        self.assertEqual(TA.__type_params__, ())
        self.assertEqual(TA.__module__, __name__)

    def test_errors(self):
        with self.assertRaises(TypeError):
            TypeAliasType()
        with self.assertRaises(TypeError):
            TypeAliasType("TA")
        with self.assertRaises(TypeError):
            TypeAliasType("TA", list, ())
        with self.assertRaises(TypeError):
            TypeAliasType("TA", list, type_params=42)
        with self.assertRaises(TypeError):
            TypeAliasType("TA", list, qualname=range(5))


class TypeAliasTypeTest(unittest.TestCase):
    def test_immutable(self):
        with self.assertRaises(TypeError):
            TypeAliasType.whatever = "not allowed"

    def test_no_subclassing(self):
        with self.assertRaisesRegex(TypeError, "not an acceptable base type"):
            class MyAlias(TypeAliasType):
                pass

    def test_union(self):
        type Alias1 = int
        type Alias2 = str
        union = Alias1 | Alias2
        self.assertIsInstance(union, types.UnionType)
        self.assertEqual(get_args(union), (Alias1, Alias2))
        union2 = Alias1 | list[float]
        self.assertIsInstance(union2, types.UnionType)
        self.assertEqual(get_args(union2), (Alias1, list[float]))
        union3 = list[range] | Alias1
        self.assertIsInstance(union3, types.UnionType)
        self.assertEqual(get_args(union3), (list[range], Alias1))

    def test_module(self):
        self.assertEqual(TypeAliasType.__module__, "typing")
        type Alias = int
        self.assertEqual(Alias.__module__, __name__)
        self.assertEqual(mod_generics_cache.Alias.__module__,
                         mod_generics_cache.__name__)
        self.assertEqual(mod_generics_cache.OldStyle.__module__,
                         mod_generics_cache.__name__)
        Alias.__module__ = "ham.spam.eggs"
        self.assertEqual(Alias.__module__, "ham.spam.eggs")

    def test_doc(self):
        type Alias = int
        """Original documentation."""

        self.assertEqual(Alias.__doc__, "Original documentation.")
        Alias.__doc__ = "Updated documentation."
        self.assertEqual(Alias.__doc__, "Updated documentation.")
        del Alias.__doc__
        self.assertIsNone(Alias.__doc__)

    def test_doc_cycle(self):
        class Doc(str):
            pass

        doc = Doc("Type alias documentation.")
        alias = TypeAliasType("Alias", int)
        alias.__doc__ = doc
        doc.alias = alias
        ref = weakref.ref(doc)
        del alias, doc
        gc_collect()
        self.assertIsNone(ref())

    def test_unpack(self):
        type Alias = tuple[int, int]
        unpacked = (*Alias,)[0]
        self.assertEqual(unpacked, Unpack[Alias])

        class Foo[*Ts]:
            pass

        x = Foo[str, *Alias]
        self.assertEqual(x.__args__, (str, Unpack[Alias]))


# All these type aliases are used for pickling tests:
T = TypeVar('T')
type SimpleAlias = int
type RecursiveAlias = dict[str, RecursiveAlias]
type GenericAlias[X] = list[X]
type GenericAliasMultipleTypes[X, Y] = dict[X, Y]
type RecursiveGenericAlias[X] = dict[str, RecursiveAlias[X]]
type BoundGenericAlias[X: int] = set[X]
type ConstrainedGenericAlias[LongName: (str, bytes)] = list[LongName]
type AllTypesAlias[A, *B, **C] = Callable[C, A] | tuple[*B]


class TypeAliasPickleTest(unittest.TestCase):
    def test_pickling(self):
        things_to_test = [
            SimpleAlias,
            RecursiveAlias,

            GenericAlias,
            GenericAlias[T],
            GenericAlias[int],

            GenericAliasMultipleTypes,
            GenericAliasMultipleTypes[str, T],
            GenericAliasMultipleTypes[T, str],
            GenericAliasMultipleTypes[int, str],

            RecursiveGenericAlias,
            RecursiveGenericAlias[T],
            RecursiveGenericAlias[int],

            BoundGenericAlias,
            BoundGenericAlias[int],
            BoundGenericAlias[T],

            ConstrainedGenericAlias,
            ConstrainedGenericAlias[str],
            ConstrainedGenericAlias[T],

            AllTypesAlias,
            AllTypesAlias[int, str, T, [T, object]],

            # Other modules:
            mod_generics_cache.Alias,
            mod_generics_cache.OldStyle,
        ]
        for thing in things_to_test:
            for proto in range(pickle.HIGHEST_PROTOCOL + 1):
                with self.subTest(thing=thing, proto=proto):
                    pickled = pickle.dumps(thing, protocol=proto)
                    self.assertEqual(pickle.loads(pickled), thing)

    type ClassLevel = str

    def test_pickling_local(self):
        type A = int
        things_to_test = [
            self.ClassLevel,
            A,
        ]
        for thing in things_to_test:
            for proto in range(pickle.HIGHEST_PROTOCOL + 1):
                with self.subTest(thing=thing, proto=proto):
                    with self.assertRaises(pickle.PickleError):
                        pickle.dumps(thing, protocol=proto)


class TypeParamsExoticGlobalsTest(unittest.TestCase):
    def test_exec_with_unusual_globals(self):
        class customdict(dict):
            def __missing__(self, key):
                return key

        code = compile("type Alias = undefined", "test", "exec")
        ns = customdict()
        exec(code, ns)
        Alias = ns["Alias"]
        self.assertEqual(Alias.__value__, "undefined")

        code = compile("class A: type Alias = undefined", "test", "exec")
        ns = customdict()
        exec(code, ns)
        Alias = ns["A"].Alias
        self.assertEqual(Alias.__value__, "undefined")
