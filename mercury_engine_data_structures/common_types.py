import copy
import typing

import construct
from construct import Adapter

from mercury_engine_data_structures.construct_extensions.strings import CStringRobust

StrId = CStringRobust("utf-8")
Int: construct.FormatField = typing.cast(construct.FormatField, construct.Int32sl)
UInt: construct.FormatField = typing.cast(construct.FormatField, construct.Int32ul)
Float: construct.FormatField = typing.cast(construct.FormatField, construct.Float32l)
CVector2D = construct.Array(2, Float)
CVector3D = construct.Array(3, Float)
CVector4D = construct.Array(4, Float)


class ListContainerWithKeyAccess(construct.ListContainer):
    def __init__(self, item_key_field: str, item_value_field: str = "value"):
        super().__init__()
        self.item_key_field = item_key_field
        self.item_value_field = item_value_field

    def _wrap(self, key, value):
        new_item = construct.Container()
        new_item[self.item_key_field] = key
        new_item[self.item_value_field] = value
        return new_item

    def __getitem__(self, key):
        for it in reversed(self):
            if it[self.item_key_field] == key:
                return it[self.item_value_field]
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        for i, it in enumerate(self):
            if i == key:
                return super().__setitem__(i, value)
            if it[self.item_key_field] == key:
                return super().__setitem__(i, self._wrap(key, value))
        self.append(value)

    def items(self):
        for it in self:
            yield it[self.item_key_field], it[self.item_value_field]


class DictAdapter(Adapter):
    def _decode(self, obj: construct.ListContainer, context, path):
        result = construct.Container()
        for item in obj:
            key = item.key
            if key in result:
                raise construct.ConstructError(f"Key {key} found twice in object", path)
            result[key] = item.value
        return result

    def _encode(self, obj: construct.Container, context, path):
        return construct.ListContainer(
            construct.Container(key=type_, value=item)
            for type_, item in obj.items()
        )


class DictElement(construct.Construct):
    def __init__(self, field, key=StrId):
        super().__init__()
        self.field = field
        self.key = key

    def _parse(self, stream, context, path):
        context = construct.Container(
            _=context, _params=context._params, _root=None, _parsing=context._parsing,
            _building=context._building, _sizing=context._sizing, _io=stream,
            _index=context.get("_index", None))
        context._root = context._.get("_root", context)

        key = self.key._parsereport(stream, context, path)
        value = self.field._parsereport(stream, context, f"{path} -> {key}")

        return construct.Container(
            key=key,
            value=value,
        )

    def _build(self, obj, stream, context, path):
        context = construct.Container(
            _=context, _params=context._params, _root=None, _parsing=context._parsing,
            _building=context._building, _sizing=context._sizing, _io=stream,
            _index=context.get("_index", None))
        context._root = context._.get("_root", context)

        key = self.key._build(obj.key, stream, context, path)
        value = self.field._build(obj.value, stream, context, f"{path} -> {key}")

        return construct.Container(
            key=key,
            value=value,
        )

    def _sizeof(self, context, path):
        context = construct.Container(
            _=context, _params=context._params, _root=None, _parsing=context._parsing,
            _building=context._building, _sizing=context._sizing, _io=None,
            _index=context.get("_index", None))
        context._root = context._.get("_root", context)

        key = self.key._sizeof(context, path)
        value = self.field._sizeof(context, f"{path} -> {key}")
        return key + value


def make_dict(value: construct.Construct, key=StrId):
    return DictAdapter(make_vector(DictElement(value, key)))


def make_vector(value: construct.Construct):
    arr = construct.Array(
        construct.this.count,
        value,
    )
    arr.name = "items"

    def get_len(ctx):
        return len(ctx['items'])

    return construct.FocusedSeq(
        "items",
        "count" / construct.Rebuild(construct.Int32ul, get_len),
        arr,
    )


def make_enum(values: typing.Union[typing.List[str], typing.Dict[str, int]], *,
              add_invalid: bool = True):
    if isinstance(values, dict):
        mapping = copy.copy(values)
    else:
        mapping = {
            name: i
            for i, name in enumerate(values)
        }
    if add_invalid:
        mapping["Invalid"] = 0x7fffffff
    return construct.Enum(construct.Int32ul, **mapping)
