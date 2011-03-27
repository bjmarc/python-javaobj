import StringIO
import struct

def loads(object):
    """
    Deserializes Java primitive data and objects serialized by ObjectOutputStream
    from a string.
    See: http://download.oracle.com/javase/6/docs/platform/serialization/spec/protocol.html
    """
    f = StringIO.StringIO(object)
    marshaller = JavaObjectMarshaller()
    return marshaller.load_stream(f)
#    ba = f.read(4)
#    (magic, version) = struct.unpack(">HH", ba)
#    print magic
#    if magic != 0xaced:
#        raise RuntimeError("The stream is not java serialized object. Magic number failed.")
#
#    print version
#
#    print type(object), Magic

def dumps(object):
    """
    Serializes Java primitive data and objects unmarshaled by load(s) before into string.
    """
    marshaller = JavaObjectMarshaller()
    return marshaller.dump(object)


class JavaClass(object):
    def __init__(self):
        self.name = None
        self.serialVersionUID = None
        self.flags = None
        self.fields_names = []
        self.fields_types = []
        self.superclass = None

    def __str__(self):
        return "[%s:0x%X]" % (self.name, self.serialVersionUID)


class JavaObject(object):
    classdesc = None

    def get_class(self):
        return self.classdesc


class JavaObjectMarshaller:

    STREAM_MAGIC = 0xaced
    STREAM_VERSION = 0x05

    TC_NULL = 0x70
    TC_REFERENCE = 0x71
    TC_CLASSDESC = 0x72
    TC_OBJECT = 0x73
    TC_STRING = 0x74
    TC_ARRAY = 0x75
    TC_CLASS = 0x76
    TC_BLOCKDATA = 0x77
    TC_ENDBLOCKDATA = 0x78
    TC_RESET = 0x79
    TC_BLOCKDATALONG = 0x7A
    TC_EXCEPTION = 0x7B
    TC_LONGSTRING = 0x7C
    TC_PROXYCLASSDESC = 0x7D
    TC_ENUM = 0x7E
    TC_MAX = 0x7E

    # classDescFlags
    SC_WRITE_METHOD = 0x01 # if SC_SERIALIZABLE
    SC_BLOCK_DATA = 0x08   # if SC_EXTERNALIZABLE
    SC_SERIALIZABLE = 0x02
    SC_EXTERNALIZABLE = 0x04
    SC_ENUM = 0x10

    def __init__(self):
        self.opmap = {
            self.TC_NULL: self.do_null,
            self.TC_CLASSDESC: self.do_classdesc,
            self.TC_OBJECT: self.do_object,
            self.TC_STRING: self.do_string,
            self.TC_ARRAY: self.do_array,
            self.TC_CLASS: self.do_class,
            self.TC_BLOCKDATA: self.do_blockdata,
            self.TC_REFERENCE: self.do_reference
        }
        self.current_object = None

    def load_stream(self, stream):
        self.object_stream = stream
        self._readStreamHeader()
        return self.readObject()

    def _readStreamHeader(self):
        (magic, version) = self._readStruct(">HH")
        if magic != self.STREAM_MAGIC or version != self.STREAM_VERSION:
            raise IOError("The stream is not java serialized object. Invalid stream header: %04X%04X" % (magic, version))

    def readObject(self):
        res = self.read_and_exec_opcode(ident=0)    # TODO: add expects

        the_rest = self.object_stream.read()
        if len(the_rest):
            print "Warning!!!!: Stream still has %s bytes left." % len(the_rest)
            print self.hexdump(the_rest)
        else:
            print "Ok!!!!"

        return res

    def read_and_exec_opcode(self, ident=0, expect=None):
        (opid, ) = self._readStruct(">B")
        self.print_ident("OpCode: 0x%X" % opid, ident)
        if expect and opid not in expect:
            raise IOError("Unexpected opcode 0x%X" % opid)
        return self.opmap.get(opid, self.do_default_stuff)(ident=ident)

    def _readStruct(self, unpack):
        length = struct.calcsize(unpack)
        ba = self.object_stream.read(length)
        return struct.unpack(unpack, ba)

    def _readString(self):
        (length, ) = self._readStruct(">H")
        ba = self.object_stream.read(length)
        return ba

    def do_classdesc(self, parent=None, ident=0):
        # TC_CLASSDESC className serialVersionUID newHandle classDescInfo
        # classDescInfo:
        #   classDescFlags fields classAnnotation superClassDesc
        # classDescFlags:
        #   (byte)                  // Defined in Terminal Symbols and Constants
        # fields:
        #   (short)<count>  fieldDesc[count]

        # fieldDesc:
        #   primitiveDesc
        #   objectDesc
        # primitiveDesc:
        #   prim_typecode fieldName
        # objectDesc:
        #   obj_typecode fieldName className1
        clazz = JavaClass()
        self.print_ident("[classdesc]", ident)
        ba = self._readString()
        clazz.name = ba
        self.print_ident("Class name: %s" % ba, ident)
        (serialVersionUID, newHandle, classDescFlags) = self._readStruct(">LLB")
        clazz.serialVersionUID = serialVersionUID
        clazz.flags = classDescFlags
        self.print_ident("Serial: 0x%X newHanle: 0x%X. classDescFlags: 0x%X" % (serialVersionUID, newHandle, classDescFlags), ident)
        (length, ) = self._readStruct(">H")
        self.print_ident("Fields num: 0x%X" % length, ident)

        clazz.fields_names = []
        clazz.fields_types = []
        for fieldId in range(length):
            (type, ) = self._readStruct(">B")
            field_name = self._readString()
            field_type = None
            field_type = self.convert_char_to_type(type)

            if field_type == "array":
                field_type = self.read_and_exec_opcode(ident=ident+1, expect=[self.TC_STRING, self.TC_REFERENCE])
                if field_type is not None:
                    field_type = "array of " + field_type
                else:
                    field_type = "array of None"
            elif field_type == "object":
                field_type = self.read_and_exec_opcode(ident=ident+1, expect=[self.TC_STRING, self.TC_REFERENCE])

            self.print_ident("FieldName: 0x%X" % type + " " + str(field_name) + " " + str(field_type), ident)
            clazz.fields_names.append(field_name)
            clazz.fields_types.append(field_type)
        if parent:
            parent.__fields = clazz.fields_names
            parent.__types = clazz.fields_types
        # classAnnotation
        (opid, ) = self._readStruct(">B")
        if opid != self.TC_ENDBLOCKDATA:
            raise NotImplementedError("classAnnotation isn't implemented yet")
        self.print_ident("OpCode: 0x%X" % opid, ident)
        # superClassDesc
        superclassdesc = self.read_and_exec_opcode(ident=ident+1, expect=[self.TC_CLASSDESC, self.TC_NULL])
        self.print_ident(str(superclassdesc), ident)
        clazz.superclass = superclassdesc

        return clazz

    def do_blockdata(self, parent=None, ident=0):
        # TC_BLOCKDATA (unsigned byte)<size> (byte)[size]
        self.print_ident("[blockdata]", ident)
        (length, ) = self._readStruct(">B")
        ba = self.object_stream.read(length)
        return ba

    def do_class(self, parent=None, ident=0):
        # TC_CLASS classDesc newHandle
        self.print_ident("[class]", ident)

        # TODO: what to do with "(ClassDesc)prevObject". (see 3rd line for classDesc:)
        classdesc = self.read_and_exec_opcode(ident=ident+1, expect=[self.TC_CLASSDESC, self.TC_PROXYCLASSDESC, self.TC_NULL])
        self.print_ident("Classdesc: %s" % classdesc, ident)
        return classdesc

    def do_object(self, parent=None, ident=0):
        # TC_OBJECT classDesc newHandle classdata[]  // data for each class
        java_object = JavaObject()
        self.print_ident("[object]", ident)

        # TODO: what to do with "(ClassDesc)prevObject". (see 3rd line for classDesc:)
        classdesc = self.read_and_exec_opcode(ident=ident+1, expect=[self.TC_CLASSDESC, self.TC_PROXYCLASSDESC, self.TC_NULL])

        # classdata[]

        # Store classdesc of this object
        java_object.classdesc = classdesc

        # classdata[]
        # TODO: nowrclass, wrclass, externalContents, objectAnnotation
        if classdesc.flags & self.SC_SERIALIZABLE and not (classdesc.flags & self.SC_WRITE_METHOD):
            pass
        else:
            raise NotImplementedError("only nowrclass is implemented.")
        # create megalist
        tempclass = classdesc
        megalist = []
        megatypes = []
        while tempclass:
            print ">>>", tempclass.fields_names, tempclass
            fieldscopy = tempclass.fields_names[:]
            fieldscopy.extend(megalist)
            megalist = fieldscopy

            fieldscopy = tempclass.fields_types[:]
            fieldscopy.extend(megatypes)
            megatypes = fieldscopy

            tempclass = tempclass.superclass

        print "Prepared list of values:", megalist
        print "Prepared list of types:", megatypes

        for field_name, field_type in zip(megalist, megatypes):
            res = self.read_native(field_type, ident)
            java_object.__setattr__(field_name, res)
        return java_object

    def do_string(self, parent=None, ident=0):
        self.print_ident("[string]", ident)
        ba = self._readString()
        return str(ba)

    def do_array(self, parent=None, ident=0):
        # TC_ARRAY classDesc newHandle (int)<size> values[size]
        self.print_ident("[array]", ident)
        classdesc = self.read_and_exec_opcode(ident=ident+1, expect=[self.TC_CLASSDESC, self.TC_PROXYCLASSDESC, self.TC_NULL])
        (size, ) = self._readStruct(">i")
        self.print_ident("size: " + str(size), ident)

        array = []

#        for char in classdesc.name:
        typestr = self.convert_char_to_type(classdesc.name[0])
        assert typestr == "array"
        typestr = self.convert_char_to_type(classdesc.name[1])

        if typestr == "object" or typestr == "array":
            for i in range(size):
                res = self.read_and_exec_opcode(ident=ident+1)
                print res
                array.append(res)
        else:
            for i in range(size):
                res = self.read_native(typestr, ident)
                print "Native value:", res
                array.append(res)
#            raise RuntimeError("Native types aren't supported in arrays")

        return None

    def do_reference(self, parent=None, ident=0):
        # TODO: Reference isn't supported yed
        (handle, reference) = self._readStruct(">HH")
        print "## Reference:", handle, reference
#        raise NotImplementedError("Reference isn't supported yed.")

    def do_null(self, parent=None, ident=0):
        return None

    def do_default_stuff(self, parent=None, ident=0):
        raise RuntimeError("Unknown OpCode")

    def print_ident(self, message, ident):
        print " " * ident + str(message)

    def hexdump(self, src, length=16):
        FILTER=''.join([(len(repr(chr(x)))==3) and chr(x) or '.' for x in range(256)])
        result = []
        for i in xrange(0, len(src), length):
            s = src[i:i+length]
            hexa = ' '.join(["%02X"%ord(x) for x in s])
            printable = s.translate(FILTER)
            result.append("%04X   %-*s  %s\n" % (i, length*3, hexa, printable))
        return ''.join(result)

    def read_native(self, field_type, ident):
        if field_type == "boolean":
            (val, ) = self._readStruct(">B")
            res = bool(val)
        elif field_type == "byte":
            (res, ) = self._readStruct(">b")
        elif field_type == "short":
            (res, ) = self._readStruct(">h")
        elif field_type == "integer":
            (res, ) = self._readStruct(">i")
        elif field_type == "long":
            (res, ) = self._readStruct(">q")
        elif field_type == "float":
            (res, ) = self._readStruct(">f")
        elif field_type == "double":
            (res, ) = self._readStruct(">d")
        else:
            res = self.read_and_exec_opcode(ident=ident+1)
        return res

    def convert_char_to_type(self, type_char):
        if type(type_char) is str:
            type_char = ord(type_char)
            
        if type_char == 0x44: # 'D': Double
            return "double"
        elif type_char == 0x49: # 'I': Integer
            return "integer"
        elif type_char == 0x4A: # 'J': Long
            return "long"
        elif type_char == 0x53: # 'S': Short
            return "short"
        elif type_char == 0x5A: # 'Z': Boolean
            return "boolean"
        elif type_char == 0x5B: # '[': Array
            return "array"
        elif type_char == 0x42: # 'B': Byte
            return "byte"
        elif type_char == 0x46: # 'F': Float
            return "float"
        elif type_char == 0x4C: # 'L': Object
            return "object"
        else:
            raise NotImplementedError("type 0x%X (%s) isn't implemented yet" % (0, type_char))

    # =====================================================================================

    def dump(self, obj):
        self.object_obj = obj
        self.object_stream = StringIO.StringIO()
        self._writeStreamHeader()
        self.writeObject(obj)
        return self.object_stream.getvalue()

    def _writeStreamHeader(self):
        self._writeStruct(">HH", 4, (self.STREAM_MAGIC, self.STREAM_VERSION))

    def writeObject(self, obj):
        print type(obj)
        print obj
        if type(obj) is JavaObject:
            print "This is java object!"
            self.write_object(obj)
        elif type(obj) is str:
            print "This is string."
            self.write_blockdata(obj)
#        (opid, ) = self._readStruct(">B")
#        print "OpCode: 0x%X" % opid
#        res = self.opmap.get(opid, self.do_default_stuff)()
#        return res

    def _writeStruct(self, unpack, length, args):
        ba = struct.pack(unpack, *args)
        self.object_stream.write(ba)

    def _writeString(self, string):
        len = len(string)
        self._writeStruct(">H", 2, (len, ))
        self.object_stream.write(string)

    def write_blockdata(self, obj, parent=None):
        self._writeStruct(">B", 1, (self.TC_BLOCKDATA, ))
        # TC_BLOCKDATA (unsigned byte)<size> (byte)[size]
        if type(obj) is str:
            print "This is string."
            self._writeStruct(">B", 1, (len(obj), ))
            self.object_stream.write(obj)

    def write_object(self, obj, parent=None):
        # TC_OBJECT classDesc newHandle classdata[]  // data for each class
#        self.current_object = JavaObject()
#        print "[object]"
        self._writeStruct(">B", 1, (self.TC_OBJECT, ))
        self._writeStruct(">B", 1, (self.TC_CLASSDESC, ))

#        print "OpCode: 0x%X" % opid
#        classdesc = self.opmap.get(opid, self.do_default_stuff)(self.current_object)
#        self.finalValue = classdesc
#        # classdata[]
#
#        # Store classdesc of this object
#        self.current_object.classdesc = classdesc
#
#        for field_name in self.current_object.__fields:
#            (opid, ) = self._readStruct(">B")
#            print "OpCode: 0x%X" % opid
#            res = self.opmap.get(opid, self.do_default_stuff)(self.current_object)
#            self.current_object.__setattr__(field_name, res)
#        return self.current_object
