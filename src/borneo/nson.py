#
# Copyright (c) 2018, 2022 Oracle and/or its affiliates. All rights reserved.
#
# Licensed under the Universal Permissive License v 1.0 as shown at
#  https://oss.oracle.com/licenses/upl/
#

from base64 import b64encode

from .serdeutil import SerdeUtil
from .serde import RequestSerializer
from .nson_protocol import *
from .common import TableLimits
from .exception import IllegalArgumentException

import borneo.operations

#
# Contains methods to serialize and deserialize NSON
#
# Maps, arrays, other supported NSON datatypes
# The supported types and their associated numeric values
# are defined in serdeutil in SerdeUtil.FIELD_VALUE_TYPE
#

class Nson(object):

    #
    # Primitive type write methods. These write NSON -- that is, they write
    # the type, then the value
    #

    @staticmethod
    def write_int(bos, value):
        bos.write_byte(SerdeUtil.FIELD_VALUE_TYPE.INTEGER)
        SerdeUtil.write_packed_int(bos, value)

    @staticmethod
    def write_boolean(bos, value):
        bos.write_byte(SerdeUtil.FIELD_VALUE_TYPE.BOOLEAN)
        bos.write_byte(value)

    @staticmethod
    def write_long(bos, value):
        bos.write_byte(SerdeUtil.FIELD_VALUE_TYPE.LONG)
        SerdeUtil.write_packed_long(bos, value)

    @staticmethod
    def write_double(bos, value):
        bos.write_byte(SerdeUtil.FIELD_VALUE_TYPE.DOUBLE)
        SerdeUtil.write_float(bos, value)

    @staticmethod
    def write_string(bos, value):
        bos.write_byte(SerdeUtil.FIELD_VALUE_TYPE.STRING)
        SerdeUtil.write_string(bos, value)

    @staticmethod
    def write_timestamp(bos, value):
        bos.write_byte(SerdeUtil.FIELD_VALUE_TYPE.TIMESTAMP)
        SerdeUtil.write_datetime(bos, value)

    @staticmethod
    def write_bytearray(bos, value):
        bos.write_byte(SerdeUtil.FIELD_VALUE_TYPE.BINARY)
        SerdeUtil.write_bytearray(bos, value, False)

    @staticmethod
    def write_number(bos, value):
        bos.write_byte(SerdeUtil.FIELD_VALUE_TYPE.NUMBER)
        SerdeUtil.write_decimal(bos, value)

    @staticmethod
    def write_type(bos, value):
        bos.write_byte(value)

    #
    # Primitive type read methods
    #

    @staticmethod
    def read_type(bis, expected_type):
        t = bis.read_byte()
        if t != expected_type:
            raise IllegalArgumentException(
                'Expected type ' + str(expected_type) + ', received type ' + t)

    @staticmethod
    def read_int(bis):
        Nson.read_type(bis, SerdeUtil.FIELD_VALUE_TYPE.INTEGER)
        return SerdeUtil.read_packed_int(bis)

    @staticmethod
    def read_long(bis):
        Nson.read_type(bis, SerdeUtil.FIELD_VALUE_TYPE.LONG)
        return SerdeUtil.read_packed_long(bis)

    @staticmethod
    def read_double(bis):
        Nson.read_type(bis, SerdeUtil.FIELD_VALUE_TYPE.DOUBLE)
        return SerdeUtil.read_float(bis)

    @staticmethod
    def read_string(bis):
        Nson.read_type(bis, SerdeUtil.FIELD_VALUE_TYPE.STRING)
        return SerdeUtil.read_string(bis)

    @staticmethod
    def read_timestamp(bis):
        Nson.read_type(bis, SerdeUtil.FIELD_VALUE_TYPE.TIMESTAMP)
        return SerdeUtil.read_datetime(bis)

    @staticmethod
    def read_number(bis):
        Nson.read_type(bis, SerdeUtil.FIELD_VALUE_TYPE.NUMBER)
        return SerdeUtil.read_decimal(bis)

    @staticmethod
    def read_bytearray(bis, skip):
        Nson.read_type(bis, SerdeUtil.FIELD_VALUE_TYPE.BINARY)
        return SerdeUtil.read_bytearray(bis, skip)

    @staticmethod
    def generate_events_from_nson(bis, handler, skip=False):
        """
        Generate NSON "events"
        """
        if handler is None and not skip:
            raise IllegalArgumentException(
                'Handler must have a value if not skipping')
        if handler is not None and handler.stop():
            return
        t = bis.read_byte();
        if t == SerdeUtil.FIELD_VALUE_TYPE.BINARY:
            value = SerdeUtil.read_bytearray(bis, skip)
            if not skip:
                handler.binary_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.BOOLEAN:
            value = bis.read_byte()
            if not skip:
                handler.boolean_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.DOUBLE:
            value = SerdeUtil.read_float(bis)
            if not skip:
                handler.double_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.INTEGER:
            value = SerdeUtil.read_packed_int(bis)
            if not skip:
                handler.integer_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.LONG:
            value = SerdeUtil.read_long(bis)
            if not skip:
                handler.long_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.STRING:
            value = SerdeUtil.read_string(bis)
            if not skip:
                handler.string_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.TIMESTAMP:
            value = SerdeUtil.read_datetime(bis)
            if not skip:
                handler.timestamp_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.NUMBER:
            value = SerdeUtil.read_number(bis)
            if not skip:
                handler.number_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.JSON_NULL:
            if not skip:
                handler.json_null_value()
        elif t == SerdeUtil.FIELD_VALUE_TYPE.NULL:
            if not skip:
                handler.null_value()
        elif t == SerdeUtil.FIELD_VALUE_TYPE.EMPTY:
            if not skip:
                handler.empty_value()
        elif t == SerdeUtil.FIELD_VALUE_TYPE.MAP:
            length = SerdeUtil.read_full_int(bis)
            if skip:
                bis.skip(length)
            else:
                num_elements = SerdeUtil.read_full_int(bis)
                handler.start_map(num_elements)
                if handler.stop():
                    return
                for i in range(0, num_elements):
                    key = SerdeUtil.read_string(bis)
                    skipfield = handler.start_map_field(key)
                    if handler.stop():
                        return
                    Nson.generate_events_from_nson(bis, handler, skipfield)
                    if handler.stop():
                        return
                    handler.end_map_field(key)
                    if handler.stop():
                        return
                handler.end_map(num_elements)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.ARRAY:
            length = SerdeUtil.read_full_int(bis)
            if skip:
                bis.skip(length)
            else:
                num_elements = SerdeUtil.read_full_int(bis)
                handler.start_array(num_elements)
                if handler.stop():
                    return
                for i in range(0, num_elements):
                    skip = handler.start_array_field(i)
                    if handler.stop():
                        return
                    Nson.generate_events_from_nson(bis, handler, skip)
                    if handler.stop():
                        return
                    handler.end_array_field(i)
                    if handler.stop():
                        return
                handler.end_array(num_elements)

        else:
            raise IllegalArgumentException(
                'Unknown value type code: ' + str(t))


    @staticmethod
    def generate_events_from_value(value, handler, skip=False):
        """
        Generate NSON "events" from a field value instance
        """
        t = SerdeUtil.get_type(value)
        if t == SerdeUtil.FIELD_VALUE_TYPE.BINARY:
            if not skip:
                handler.binary_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.BOOLEAN:
            if not skip:
                handler.boolean_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.DOUBLE:
            if not skip:
                handler.double_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.INTEGER:
            if not skip:
                handler.integer_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.LONG:
            if not skip:
                handler.long_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.STRING:
            if not skip:
                handler.string_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.TIMESTAMP:
            if not skip:
                handler.timestamp_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.NUMBER:
            if not skip:
                handler.number_value(value)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.JSON_NULL:
            if not skip:
                handler.json_null_value()
        elif t == SerdeUtil.FIELD_VALUE_TYPE.NULL:
            if not skip:
                handler.null_value()
        elif t == SerdeUtil.FIELD_VALUE_TYPE.EMPTY:
            if not skip:
                handler.empty_value()
        elif t == SerdeUtil.FIELD_VALUE_TYPE.MAP:
            if skip:
                return
            num_elements = len(value)
            handler.start_map(num_elements)
            if handler.stop():
                return
            for key in value:
                skipfield = handler.start_map_field(key)
                if handler.stop():
                    return
                Nson.generate_events_from_value(value[key],
                                                handler,
                                                skipfield)
                if handler.stop():
                    return
                handler.end_map_field(key)
                if handler.stop():
                    return
            handler.end_map(num_elements)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.ARRAY:
            if skip:
                return
            num_elements = len(value)
            handler.start_array(num_elements)
            if handler.stop():
                return
            index = 0
            for item in value:
                skip = handler.start_array_field(index)
                index += 1
                if handler.stop():
                    return
                Nson.generate_events_from_value(item, handler, skip)
                if handler.stop():
                    return
                handler.end_array_field(index)
                if handler.stop():
                    return
            handler.end_array(num_elements)
        else:
            raise IllegalArgumentException(
                'Unknown value type code: ' + str(t))

class NsonEventHandler:
    def boolean_value(self, value):
        pass

    def binary_value(self, value):
        pass

    def string_value(self, value):
        pass

    def integer_value(self, value):
        pass

    def long_value(self, value):
        pass

    def double_value(self, value):
        pass

    def number_value(self, value):
        pass

    def timestamp_value(self, value):
        pass

    def json_null_value(self):
        pass

    def null_value(self):
        pass

    def empty_value(self):
        pass

    def start_map(self, size=None):
        pass

    def start_array(self, size=None):
        pass

    def end_map(self, size=None):
        pass

    def end_array(self, size=None):
        pass

    def start_map_field(self, key):
        pass

    def end_map_field(self, key=None):
        pass

    def start_array_field(self, index=None):
        pass

    def end_array_field(self, index=None):
        pass

    def stop(self):
        return False

class NsonSerializer(NsonEventHandler):
    """
    This class serializes an NSON "document." It maintains state for nested
    maps and arrays.
    """
    def __init__(self, bos):
        # output stream
        self._bos = bos

        # stack of offsets for map and array total size in bytes
        self._offset_stack = []

        # stack of offsets for tracking number of elements in a map or array
        self._size_stack = []

    def get_stream(self):
        return self._bos

    def binary_value(self, value):
        Nson.write_bytearray(self._bos, value)

    def boolean_value(self, value):
        Nson.write_boolean(self._bos, value)

    def double_value(self, value):
        Nson.write_double(self._bos, value)

    def empty_value(self):
        Nson.write_type(self._bos, SerdeUtil.FIELD_VALUE_TYPE.EMPTY)

    def integer_value(self, value):
        Nson.write_int(self._bos, value)

    def json_null_value(self):
        Nson.write_type(self._bos, SerdeUtil.FIELD_VALUE_TYPE.JSON_NULL)

    def long_value(self, value):
        Nson.write_long(self._bos, value)

    def null_value(self):
        Nson.write_type(self._bos, SerdeUtil.FIELD_VALUE_TYPE.NULL)

    def number_value(self, value):
        Nson.write_number(self._bos, value)

    def string_value(self, value):
        Nson.write_string(self._bos, value)

    def timestamp_value(self, value):
        Nson.write_timestamp(self._bos, value)

    def start_map(self, size=None):
        self._start_map_or_array(SerdeUtil.FIELD_VALUE_TYPE.MAP)

    def start_array(self, size=None):
        self._start_map_or_array(SerdeUtil.FIELD_VALUE_TYPE.ARRAY)

    def _start_map_or_array(self, field_type):
        self._bos.write_byte(field_type);
        offset = self._bos.get_offset()
        self._bos.write_int(0) # size in bytes
        self._bos.write_int(0) # number of elements
        self._offset_stack.append(offset)
        self._size_stack.append(0)

    def end_map(self, size=None):
        self._end_map_or_array()

    def end_array(self, size=None):
        self._end_map_or_array()

    def _end_map_or_array(self):
        length_offset = self._offset_stack.pop()
        num_elems = self._size_stack.pop()
        start = length_offset + 4
        total_bytes = self._bos.get_offset() - start
        # total # bytes followed by number of elements
        SerdeUtil.write_int_at_offset(self._bos, length_offset, total_bytes)
        SerdeUtil.write_int_at_offset(self._bos, length_offset + 4, num_elems)

    def start_map_field(self, field_name):
        # no type to write so use SerdeUtil
        SerdeUtil.write_string(self._bos, field_name)

    def end_map_field(self, field_name=None):
        self._incr_size() # add 1 to number of elements

    def end_array_field(self, index=0):
        self._incr_size() # add 1 to number of elements

    def _incr_size(self):
        # add one to value on top of size stack. Using an index of -1
        # refers to the last element in the array/list
        self._size_stack[-1] += 1

class MapWalker(object):
    """
    This class "walks" an NSON map, allowing a caller to see each field and
    read each field. It is up to the caller to either (1) deserialize the
    field or (2) call skip() to move to the next one
    """
    # prevent an infinite loop in the event of bad deserialization
    MAX_ELEMS = 10000000

    def __init__(self, bis):
        self._bis = bis
        self._current_name = None
        self._current_index = 0;
        t = bis.read_byte()
        if t != SerdeUtil.FIELD_VALUE_TYPE.MAP:
            raise IllegalArgumentException(
                'NSON MapWalker: stream must be located at a MAP')
        SerdeUtil.read_full_int(bis) # total length in bytes, not relevant
        self._num_elements = SerdeUtil.read_full_int(bis)
        if self._num_elements < 0 or self._num_elements > MapWalker.MAX_ELEMS:
            raise IllegalArgumentException(
                'NSON MapWalker: invalid number of elements: ' +
                str(self._num_elements))

    def get_current_name(self):
        return self._current_name

    def get_stream(self):
        return self._bis

    def has_next(self):
        return self._current_index < self._num_elements

    def next(self):
        if self._current_index >= self._num_elements:
            raise IllegalArgumentException(
                'Cannot call next with no elements remaining')
        self._current_name = SerdeUtil.read_string(self._bis)
        self._current_index += 1

    def skip(self):
        t = self._bis.read_byte()
        if (t == SerdeUtil.FIELD_VALUE_TYPE.MAP or
            t == SerdeUtil.FIELD_VALUE_TYPE.ARRAY):
            length = SerdeUtil.read_full_int(self._bis)
            self._bis.skip(length)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.BINARY:
            SerdeUtil.read_bytearray(self._bis, True)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.BOOLEAN:
            self._bis.read_byte()
        elif t == SerdeUtil.FIELD_VALUE_TYPE.DOUBLE:
            SerdeUtil.read_float(self._bis)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.INTEGER:
            SerdeUtil.read_packed_int(self._bis)
        elif t == SerdeUtil.FIELD_VALUE_TYPE.LONG:
            SerdeUtil.read_long(self._bis)
        elif (t == SerdeUtil.FIELD_VALUE_TYPE.STRING or
              t == SerdeUtil.FIELD_VALUE_TYPE.TIMESTAMP or
              t == SerdeUtil.FIELD_VALUE_TYPE.NUMBER):
            SerdeUtil.read_string(self._bis)
        elif (t == SerdeUtil.FIELD_VALUE_TYPE.JSON_NULL or
              t == SerdeUtil.FIELD_VALUE_TYPE.NULL or
              t == SerdeUtil.FIELD_VALUE_TYPE.EMPTY):
            return
        else:
            raise IllegalArgumentException('Unknown field type: ' + str(t))

class JsonSerializer(NsonEventHandler):
    QUOTE ='"'
    COMMA=','
    comma_value = 44
    CR = '\n'
    SP = ' '
    SEP = ' : '

    #
    # Each individually appended piece of JSON is kept in a string that is a
    # member of a list, _builder. The final concatenation is done with a
    # list join() call.
    #
    # Pretty-printing is an option that results in object files on their own
    # lines and indentation for nested objects
    #
    def __init__(self, pretty = False):
        self._builder = []
        self._pretty = pretty
        self._current_indent = 0
        self._incr = 2
        self._indent = ''
        if pretty:
            self._sep = ' : '
        else:
            self._sep = ':'

    def boolean_value(self, value):
        self._append(value, False)

    def binary_value(self, value):
        self._append(b64encode(value), True)

    def string_value(self, value):
        self._append(str(value), True)

    def integer_value(self, value):
        self._append(str(value), False)

    def long_value(self, value):
        self._append(str(value), False)

    def double_value(self, value):
        self._append(str(value), False)

    def number_value(self, value):
        self._append(str(value), False)

    def timestamp_value(self, value):
        self._append(str(value), True)

    def json_null_value(self):
        self._append('null', False)

    def null_value(self):
        self._append('null', False)

    def empty_value(self):
        self._append('EMPTY', True)

    def start_map(self, size=None):
        self._append('{', False)
        self._change_indent(self._incr)

    def start_array(self, size=None):
        self._append('[', False)

    def end_map(self, size=None):
        if self._builder[-1] == self.COMMA:
            self._builder.pop()
        if self._pretty:
            self._change_indent(-(self._incr))
            self._append(self.CR, False)
            self._append(self._indent, False)

        self._append('}', False)

    def end_array(self, size=None):
        if self._builder[-1] == self.COMMA:
            self._builder.pop()
        self._append(']', False)

    def start_map_field(self, key):
        if self._pretty:
            self._append(self.CR, False)
            self._append(self._indent, False)
        self._append(key, True)
        self._append(self._sep, False)

    def end_map_field(self, key=None):
        self._append(',', False)

    def start_array_field(self, index=None):
        pass

    def end_array_field(self, index=None):
        self._append(',', False)

    def stop(self):
        return False

    def _append(self, val, quote):
        if quote:
            self._quote()
        self._builder.append(val)
        if quote:
            self._quote()

    def _quote(self):
        self._builder.append(self.QUOTE)

    def _change_indent(self, num):
        if self._pretty:
            self._current_indent += num
            new_indent = []
            if self._current_indent == 0:
                self._indent = ''
            for i in range(self._current_indent):
                new_indent.append(self.SP)
                self._indent = "".join(new_indent)

    def __str__(self):
        return "".join(self._builder)

#
# Here down... request serializers
#

class GetTableRequestSerializer(RequestSerializer):

    def serialize(self, request, bos, serial_version):
        ns = NsonSerializer(bos)
        ns.start_map() # top-level object

        # header
        Proto.start_map(ns, HEADER)
        Proto.write_header(ns, SerdeUtil.OP_CODE.GET_TABLE, request)
        Proto.end_map(ns, HEADER)

        # payload
        Proto.start_map(ns, PAYLOAD)
        Proto.write_string_map_field(ns, OPERATION_ID,
                                     request.get_operation_id())
        Proto.end_map(ns, PAYLOAD)

        ns.end_map() # top-level object

    def deserialize(self, request, bis, serial_version):
        return Proto.deserialize_table_result(bis)


class Proto(object):
    #
    # Common methods for serializers
    #

    @staticmethod
    def write_header(ns, op, request):
        Proto.write_int_map_field(ns, VERSION,
                                  SerdeUtil.SERIAL_VERSION_4)
        if request.get_table_name() is not None:
            Proto.write_string_map_field(ns, TABLE_NAME,
                                         request.get_table_name())
        Proto.write_int_map_field(ns, OP_CODE, op)
        Proto.write_int_map_field(ns, TIMEOUT, request.get_timeout())

    # atomic fields
    # Java uses type-specific overloads to differentiate the atomic values
    # integer, string, boolean, binary
    # All of the callers know the type, so in Python make it part of the
    # method vs checking types, which is inefficient
    #
    @staticmethod
    def write_int_map_field(ns, name, value):
        ns.start_map_field(name)
        ns.integer_value(value)
        ns.end_map_field(name)

    @staticmethod
    def write_string_map_field(ns, name, value):
        ns.start_map_field(name)
        ns.string_value(value)
        ns.end_map_field(name)

    @staticmethod
    def write_bool_map_field(ns, name, value):
        ns.start_map_field(name)
        ns.boolean_value(value)
        ns.end_map_field(name)

    @staticmethod
    def write_bin_map_field(ns, name, value):
        ns.start_map_field(name)
        ns.binary_value(value)
        ns.end_map_field(name)

    #
    # start/end complex types
    #
    @staticmethod
    def start_map(ns, name):
        ns.start_map_field(name)
        ns.start_map()

    @staticmethod
    def end_map(ns, name):
        ns.end_map()
        ns.end_map_field(name)

    #
    # Objects shared among request types
    #
    @staticmethod
    def deserialize_table_result(bis):
        result = borneo.operations.TableResult()
        # save and reset offset in stream
        saved_offset = bis.get_offset()
        bis.set_offset(0)
        walker = MapWalker(bis)

        while walker.has_next():
            walker.next()
            name = walker.get_current_name()
            if name == ERROR_CODE:
                Proto.handle_error_code(walker)
            elif name == COMPARTMENT_OCID:
                result.set_compartment_id(Nson.read_string(bis))
            elif name == NAMESPACE:
                result.set_namespace(Nson.read_string(bis))
            elif name == TABLE_OCID:
                result.set_table_ocid(Nson.read_string(bis))
            elif name == TABLE_NAME:
                result.set_table_name(Nson.read_string(bis))
            elif name == TABLE_STATE:
                result.set_state(SerdeUtil.get_table_state(
                    Nson.read_int(bis)))
            elif name == TABLE_SCHEMA:
                result.set_schema(Nson.read_string(bis))
            elif name == TABLE_DDL:
                result.set_ddl(Nson.read_string(bis))
            elif name == OPERATION_ID:
                result.set_operation_id(Nson.read_string(bis))
            elif name == FREE_FORM_TAGS:
                # TODO
                walker.skip()
            elif name == DEFINED_TAGS:
                # TODO
                walker.skip()
            elif name == ETAG:
                result.set_match_etag(Nson.read_string(bis))
            elif name == LIMITS:
                lw = MapWalker(bis)
                ru = 0
                wu = 0
                sg = 0
                mode = SerdeUtil.CAPACITY_MODE.PROVISIONED
                while lw.has_next():
                    lw.next()
                    name = lw.get_current_name()
                    if name == READ_UNITS:
                        ru = Nson.read_int(bis)
                    elif name == WRITE_UNITS:
                        wu = Nson.read_int(bis)
                    elif name == STORAGE_GB:
                        sg = Nson.read_int(bis)
                    elif name == LIMITS_MODE:
                        mode = Nson.read_int(bis)
                    else:
                        lw.skip()
                result.set_table_limits(TableLimits(ru, wu, sg, mode))
            else:
                # log/warn?
                walker.skip()
        return result

    #
    # Handle success/failure in a response. Success is a 0 error code.
    # Failure is a non-zero code and may also include:
    #  Exception message
    #  Consumed capacity
    #  Retry hints if throttling (future)
    # This method throws an appropriately mapped exception on error and
    # nothing on success.
    #
    #   "error_code": int (code)
    #   "exception": "..."
    #   "consumed": {
    #      "read_units": int,
    #      "read_kb": int,
    #      "write_kb": int
    #    }
    #
    # The walker must be positioned at the very first field in the response
    # which *must* be the error code.
    #
    # This method either returns a non-zero error code or throws an
    # exception based on the error code and additional information.

    @staticmethod
    def handle_error_code(walker):
        bis = walker.get_stream()
        code = Nson.read_int(bis)
        if code == 0:
            return
        msg = None
        while walker.has_next():
            walker.next()
            name = walker.get_current_name()
            if name == EXCEPTION:
                msg = Nson.read_string(bis)
                raise SerdeUtil.map_exception(code, msg)
            elif name == CONSUMED:
                # TODO -- this means delaying raise until end
                walker.skip()
            else:
                walker.skip()
