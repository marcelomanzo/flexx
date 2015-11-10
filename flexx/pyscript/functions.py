import os
import sys
import types
import inspect
import subprocess
import hashlib

from . import Parser

if sys.version_info[0] >= 3:
    string_types = str,
    text_type = str
else:  # pragma: no cover
    string_types = basestring,
    text_type = unicode


class JSString(text_type):
    """ A subclass of string, so we can add attributes to JS string objects.
    """
    pass


def py2js(ob=None, new_name=None, **parser_options):
    """ Convert Python to JavaScript.
    
    Parameters:
        ob (str, function, class): The code, function or class to transpile.
        new_name (str, optional): If given, renames the function or
            class. This argument is ignored if ob is a string.
        parser_options: Additional options for the parser. See Parser class
            for details.
    
    Returns:
        jscode (str): The JavaScript code. Also has a ``pycode`` attribute.
    
    Notes:
        The Python source code for a class is acquired by name.
        Therefore one should avoid decorating classes in modules where
        multiple classes with the same name are defined. This is a
        consequence of classes not having a corresponding code object (in
        contrast to functions).
    
    """
    
    def py2js_(ob):
        if isinstance(ob, string_types):
            thetype = 'str'
            pycode = ob
        elif isinstance(ob, type) or isinstance(ob, (types.FunctionType,
                                                     types.MethodType)):
            thetype = 'class' if isinstance(ob, type) else 'def'
            # Get code
            try:
                lines, linenr = inspect.getsourcelines(ob)
            except Exception as err:
                raise ValueError('Could not get source code for object %r: %s' %
                                 (ob, err))
            # Normalize indentation
            indent = len(lines[0]) - len(lines[0].lstrip())
            lines = [line[indent:] for line in lines]
            # Skip any decorators
            while not lines[0].lstrip().startswith(thetype):
                lines.pop(0)
            # join lines and rename
            pycode = ''.join(lines)
        else:
            raise ValueError('py2js() only accepts classes and real functions.')
        
        # Get hash, in case we ever want to cache JS accross sessions
        h = hashlib.sha256('pyscript version 1'.encode())
        h.update(pycode.encode())
        hash = h.digest()
        
        # Get JS code
        p = Parser(pycode, **parser_options)
        jscode = p.dump()
        if new_name and thetype in ('class', 'def'):
            jscode = js_rename(jscode, ob.__name__, new_name)
        
        # Wrap in JSString
        jscode = JSString(jscode)
        jscode.pycode = pycode
        jscode.pyhash = hash
        
        return jscode
    
    if ob is None:
        return py2js_  # uses as a decorator with some options set
    return py2js_(ob)


def js_rename(jscode, cur_name, new_name):
    """ Rename a function or class in a JavaScript code string.
    
    Parameters:
        jscode (str): the JavaScript source code
        cur_name (str): the current name
        new_name (str): the name to replace the current name with
    
    Returns:
        jscode (str): the modified JavaScript source code
    """
    
    jscode = jscode.replace('%s = function' % cur_name, 
                            '%s = function' % (new_name), 1)
    jscode = jscode.replace('%s.prototype' % cur_name, 
                            '%s.prototype' % new_name)
    if '.' in new_name:
        jscode = jscode.replace('var %s;\n' % cur_name, '', 1)
    else:
        jscode = jscode.replace('var %s;\n' % cur_name, 
                                'var %s;\n' % new_name, 1)
    return jscode


NODE_EXE = None
def get_node_exe():
    """ Small utility that provides the node exe. The first time this
    is called both 'nodejs' and 'node' are tried. To override the
    executable path, set the ``FLEXX_NODE_EXE`` environment variable.
    """
    # This makes things work on Ubuntu's nodejs as well as other node
    # implementations, and allows users to set the node exe if necessary
    global NODE_EXE
    NODE_EXE = os.getenv('FLEXX_NODE_EXE') or NODE_EXE
    if NODE_EXE is None:
        NODE_EXE = 'nodejs'
        try:
            subprocess.check_output([NODE_EXE, '-v'])
        except Exception:  # pragma: no cover
            NODE_EXE = 'node'
    return NODE_EXE


def evaljs(jscode, whitespace=True):
    """ Evaluate JavaScript code in Node.js.
    
    parameters:
        jscode (str): the JavaScript code to evaluate.
        whitespace (bool): if whitespace is False, the whitespace
            is removed from the result.
    
    returns:
        result (str): the last result as a string.
    """
    res = subprocess.check_output([get_node_exe(), '--use_strict', '-p', '-e', jscode])
    res = res.decode().rstrip()
    if res.endswith('undefined'):
        res = res[:-9].rstrip()
    if not whitespace:
        res = res.replace('\n', '').replace('\t', '').replace(' ', '')
    return res


def evalpy(pycode, whitespace=True):
    """ Evaluate PyScript code in Node.js (after translating to JS).
    
    parameters
    ----------
    pycode : str
        the PyScript code to evaluate.
    whitespace : bool
        if whitespace is False, the whitespace is removed from the result.
    
    returns
    -------
    result : str
        the last result as a string.
    """
    # delibirate numpy doc style to see if napoleon handles it the same
    return evaljs(py2js(pycode), whitespace)


def script2js(filename, namespace=None, target=None):
    """ Export a .py file to a .js file.
    
    Parameters:
      filename (str): the filename of the .py file to transpile.
      namespace (str): the namespace for this module. (optional)
      target (str): the filename of the resulting .js file. If not given
        or None, will use the ``filename``, but with a ``.js`` extension.
    
    """
    # Import
    assert filename.endswith('.py')
    pycode = open(filename, 'rt', encoding='utf-8').read()
    # Convert
    jscode = Parser(pycode, namespace).dump()
    jscode = '/* Do not edit, autogenerated by flexx.pyscript */\n\n' + jscode
    # Export
    if target is None:
        dirname, fname = os.path.split(filename)
        filename2 = os.path.join(dirname, fname[:-3] + '.js')
    else:
        filename2 = target
    with open(filename2, 'wb') as f:
        f.write(jscode.encode())
# 
# 
# def clean_code(code):
#     """ Remove duplicate declarations of std function definitions.
#     
#     Use this if you build a JS source file from multiple snippets and
#     want to get rid of the function declarations like ``_truthy`` and
#     ``sum``.
#     
#     Parameters:
#         code (str): the complete source code.
#     
#     Returns:
#         new_code (str): the code with duplicate definitions filtered out.
#     """
#     return code
#     # todo: remove this function
#     known_funcs = {}
#     
#     lines = []
#     for line in code.splitlines():
#         line2 = line.lstrip()
#         indent = len(line) - len(line2)
#         if line2.startswith('var ') and ' = function ' in line2:
#             prev_indent = known_funcs.get(line2, 999)
#             if prev_indent == 0 :
#                 continue
#             if indent == 0:
#                 known_funcs[line2] = indent
#         lines.append(line)
#     return '\n'.join(lines)
