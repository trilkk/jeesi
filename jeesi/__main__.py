#!/usr/bin/env python3

import argparse
import copy
import json
import pathlib
import platform
import re
import sys

from jeesi.common import append_to_path_list
from jeesi.common import find_path
from jeesi.common import is_verbose
from jeesi.common import pop_verbose
from jeesi.common import push_verbose
from jeesi.common import run_command
from jeesi.single_file_http_server import get_single_file_http_server_help
from jeesi.single_file_http_server import start_single_file_http_server
from jeesi.template import Template

########################################
# Globals ##############################
########################################

g_closure_compiler_src_dirname = "closure-compiler"
g_closure_compiler_jar_path = pathlib.Path("bazel-bin")
g_closure_compiler_jar_name = pathlib.Path("compiler_uberjar_deploy.jar")
g_default_browser = "firefox"
g_default_windows_browser_path = pathlib.Path("C:\\") / "Program Files" / "Mozilla Firefox" / "firefox.exe"
g_default_port = 8080
g_default_output_file = "index.html"
g_default_substitutions_file = "substitutions.json"

########################################
# Templates ############################
########################################

g_canvas_variable_name = "CANVAS_VARIABLE"
g_header_template = Template("<html><body style=\"margin:0;background:#000\"><canvas id=[[%s]]></canvas><script>" % (g_canvas_variable_name))
g_footer = Template("</script></body></html>")
g_externs_template_content = "var onclick;\nvar innerWidth;\nvar innerHeight;"

########################################
# Functions ############################
########################################

def find_closure_compiler_from_file_list(search_paths):
    """Try to find Closure Compiler from file listings."""
    g_re_closure_compiler = re.compile(r'^closure[-_]compiler.*\.jar$')
    for ii in search_paths:
        for jj in ii.iterdir():
            if jj.is_file() and g_re_closure_compiler.match(jj.name.lower()):
                return ii / jj
    return None

def find_closure_compiler(program_path):
    """Tries to find closure compiler."""
    search_paths = [pathlib.Path.cwd()]
    search_paths = append_to_path_list(search_paths, program_path)
    for ii in search_paths:
        closure_compiler_src = find_path(ii, g_closure_compiler_src_dirname)
        if closure_compiler_src:
            break
    if not closure_compiler_src:
        if ret := find_closure_compiler_from_file_list(search_paths):
            return ret
        raise RuntimeError("could not find '%s', tried: %s" % (g_closure_compiler_src_dirname, list(map(lambda x: str(x), search_paths))))
    ret = closure_compiler_src / g_closure_compiler_jar_path
    if not ret.is_dir():
        if ret := find_closure_compiler_from_file_list(search_paths):
            return ret
        raise RuntimeError("Closure Compiler build path '%s' not found or is not a directory" % (str(closure_compiler_jar_path)))
    ret = ret / g_closure_compiler_jar_name
    if not ret.is_file():
        if ret := find_closure_compiler_from_file_list(search_paths):
            return ret
        raise RuntimeError("Closure Compiler .jar '%s' not found or is not a file" % (str(closure_compiler_jar_path)))
    return ret

def integer_array_permutate(lst, max_index):
    """Get the next permutation of lst with max_index, return None if at end."""
    ret = copy.copy(lst)
    for ii in range(len(ret)):
        current_index = -ii - 1
        current_value = ret[current_index]
        current_value += 1
        if current_value < max_index:
            ret[current_index] = current_value
            return ret
        ret[current_index] = 0
    return None

def integer_array_has_duplicates(lst):
    """Checks if an integer array has duplicates."""
    for ii in range(len(lst)):
        current_value = lst[ii]
        for jj in range(ii + 1, len(lst)):
            if lst[jj] == current_value:
                return True
    return False

def require_regular_file(op):
    """Require given string to resolve a path to a regular file."""
    ret = pathlib.Path(op)
    if not ret.exists():
        raise RuntimeError("file '%s' does not exist" % (str(ret)))
    if not ret.is_file():
        raise RuntimeError("not a regular file: '%s'" % (str(ret)))
    return ret

def run_compression(
        header_template,
        js_template_content,
        externs_template_content,
        substitutions,
        template_file,
        externs_file,
        minified_file,
        output_file,
        compressed_file,
        closure_compiler):
    """Runs the whole compression process with given substitutions."""
    js_template = Template(js_template_content)
    js_content = js_template.format(substitutions)
    # Run Closure Compiler to shrink JavaScript input.
    if closure_compiler:
        for ii in substitutions.keys():
            externs_template_content += "\nvar [[%s]];" % (ii)
        externs_template = Template(externs_template_content)
        externs_content = externs_template.format(substitutions)
        with externs_file.open("w") as fd:
            fd.write(externs_content)
        with template_file.open("w") as fd:
            fd.write(js_content)
        closure_compiler_exec = [
                "java",
                "-jar", str(closure_compiler),
                "--compilation_level", "ADVANCED",
                "--warning_level", "VERBOSE",
                "--externs", str(externs_file),
                "--js", str(template_file),
                "--js_output_file", str(minified_file)]
        closure_compiler_stdout, closure_compiler_stderr = run_command(closure_compiler_exec)
        if is_verbose() and closure_compiler_stdout:
            print(closure_compiler_stdout)
        if not minified_file.is_file():
            raise RuntimeError("Closure Compiler output '%s' not found or is not a file" % (str(minified_file)))
        if is_verbose():
            print("Minified: '%s' -> '%s' (%i to %i bytes)" % (str(template_file), str(minified_file), template_file.stat().st_size, minified_file.stat().st_size))
    else:
        # No closure compiler, so write input to directly to minified.
        with minified_file.open("w") as fd:
            fd.write(js_content)
        if is_verbose():
            print("Nonminified input: '%s' (%i bytes)" % (str(minified_file), minified_file.stat().st_size))
    # Write uncompressed output.
    minified_input = minified_file.read_text().strip()
    if closure_compiler:
        minified_input = minified_input.replace("\n", "")
    uncompressed_output = header_template.format(substitutions) + minified_input + g_footer.format()
    with output_file.open("w") as fd:
        fd.write(uncompressed_output)
    # Compression phase.
    if closure_compiler:
        # Remove compressed file before compressing.
        if compressed_file.exists():
            if not compressed_file.is_file():
                raise RuntimeError("compressed file '%s' already exists and is not a regular file" % (str(compressed_file)))
            compressed_file.unlink()
        run_command(["brotli", "-q", "11", str(output_file), "-o", str(compressed_file)])
        ret = compressed_file.stat().st_size
        if is_verbose():
            print("Compressed: '%s' -> '%s' (%i to %i bytes)" % (str(output_file), str(compressed_file), output_file.stat().st_size, ret))
        return ret
    else:
        # Skipping Closure Compiler also skips compression.
        ret = output_file.stat().st_size
        if is_verbose():
            print("Wrote: '%s' (%i bytes)" % (str(output_file), ret))
    return ret

def single_character_alphabet():
    """Returns an alphabet of single characters, lower and upper case."""
    ret = ["_"]
    for ii in range(ord("a"), ord("z") + 1):
        ret += [chr(ii)]
    for ii in range(ord("A"), ord("Z") + 1):
        ret += [chr(ii)]
    return ret

########################################
# Main #################################
########################################

def main():
    """Main function."""
    browser = g_default_windows_browser_path if platform.system() == "Windows" else g_default_browser
    input_file = None
    closure_compiler = None

    program_path = pathlib.Path(sys.argv[0])
    program_name = program_path.name

    parser = argparse.ArgumentParser(usage="%s [options] <input>" % (program_name), add_help=False, formatter_class=argparse.RawDescriptionHelpFormatter, description="""Default settings:
    Browser:              '%s'
    Closure Compiler:     autodetect
    Output file:          '%s'
    Substitutions file:   '%s'""" % (
        browser,
        g_default_output_file,
        g_default_substitutions_file))
    parser.add_argument("-b", "--browser", action="store", default=browser, help="Specify browser binary")
    parser.add_argument("-c", "--closure-compiler", action="store", help="Path to Closure Compiler")
    parser.add_argument("-e", "--exhaustive", action="store_true", help="Exhaustively search single character variable name")
    parser.add_argument("-h", "--help", action="help", help="Print this help message and exit")
    parser.add_argument("-n", "--no-minify", action="store_true", help="Skip minification")
    parser.add_argument("-o", "--output-file", action="store", default=g_default_output_file, help="Output file to write")
    parser.add_argument("-p", "--port", action="store", default=str(g_default_port), help="Port for the single file HTTP server (default: %i)" % (g_default_port))
    parser.add_argument("-r", "--run", action="store_true", help="Run in browser after compilation")
    parser.add_argument("-s", "--start-http-server", action="store_true", help="Start a server for serving the compressed output")
    parser.add_argument("-u", "--substitutions-file", action="store", default=g_default_substitutions_file, help="Set substitutions file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print more info about what is being done")
    parser.add_argument("input", action="store", nargs="?", help="Input file")

    args = parser.parse_args()

    if args.verbose:
        push_verbose(True)

    if not args.port.isdigit():
        raise RuntimeError("port string '%s' is not an integer" % (args.port))
    server_port = int(args.port)

    if not args.output_file:
        raise RuntimeError("invalid output file: '%s'" % (str(args.output_file)))
    output_file = pathlib.Path(args.output_file)
    output_suffixes = output_file.suffixes
    if (len(output_suffixes) > 0) and (output_suffixes[-1].lower() == ".br"):
        output_suffixes.pop()
    output_suffix = output_suffixes[-1].lower() if (len(output_suffixes) > 0) else ""
    if output_suffix not in (".htm", ".html"):
        raise RuntimeError("output file '%s' has invalid suffix" % (str(output_file)))
    if output_file.exists() and (not output_file.is_file()):
        raise RuntimeError("output file '%s' already exists and is not a regular file" % (str(output_file)))
    compressed_file = None if args.no_minify else output_file.parent / (str(output_file) + ".br")

    if not args.input:
        # Starting a server means input is not needed.
        if args.start_http_server:
            thr = start_single_file_http_server(server_port, output_file, compressed_file)
            print(get_single_file_http_server_help(server_port))
            if args.run:
                run_command([args.browser, "http://localhost:%i" % (server_port)])
            sys.exit(0)
        parser.print_help(sys.stdout)
        sys.exit(0)
    input_file = require_regular_file(args.input)
    input_content = input_file.read_text().strip()
    externs_file = input_file.parent / (input_file.stem + ".externs.js")
    template_file = input_file.parent / (input_file.stem + ".templated.js")
    minified_file = input_file.parent / (input_file.stem + ".minified.js")

    # Find closure compiler unless no_minify.
    if not args.no_minify:
        if args.closure_compiler:
            closure_compiler = pathlib.Path(args.closure_compiler)
            if is_verbose():
                print("Using Closure Compiler: %s" % (str(closure_compiler)))
        if not closure_compiler:
            closure_compiler = find_closure_compiler(program_path.parent.resolve())
            if is_verbose():
                print("Found Closure Compiler: %s" % (str(closure_compiler)))

    # Read substitutions file.
    subst = {}
    substitutions_file = require_regular_file(args.substitutions_file)
    with substitutions_file.open('r') as fd:
        substitutions_json_data = json.load(fd)
    for ii in substitutions_json_data:
        subst[ii] = substitutions_json_data[ii]

    # Either permutate canvas variable name or select the predefined one.
    smallest_output = 0xFFFFFFFF
    best_substitutions = None
    if args.exhaustive:
        alphabet = single_character_alphabet()
        keys = list(subst.keys())
        # Create initial indices array (with no duplicates).
        indices = [0]
        for ii in range(1, len(keys)):
            indices += [indices[-1] + 1]
        # Loop indices until permutation does not find a solution.
        while indices:
            if integer_array_has_duplicates(indices):
                indices = integer_array_permutate(indices, len(alphabet))
                continue
            for ii in range(len(keys)):
                subst[keys[ii]] = alphabet[indices[ii]]
            push_verbose(False)
            output_size = run_compression(g_header_template, input_content, g_externs_template_content, subst, template_file, externs_file, minified_file, output_file, compressed_file, closure_compiler)
            pop_verbose()
            if output_size < smallest_output:
                smallest_output = output_size
                best_substitutions = copy.copy(subst)
                if is_verbose():
                    print("%s => %i bytes" % (str(best_substitutions), smallest_output))
            elif is_verbose():
                current_alphabet = "".join(map(lambda x: "%s" % (alphabet[x]), indices))
                print(" %s\r" % ("".join(map(lambda x: "%s" % (alphabet[x]), indices))), end = '')
                sys.stdout.flush()
            indices = integer_array_permutate(indices, len(alphabet))
        subst = best_substitutions
    # Write output.
    run_compression(g_header_template, input_content, g_externs_template_content, subst, template_file, externs_file, minified_file, output_file, compressed_file, closure_compiler)

    # Start server to run built binary.
    if args.start_http_server:
        thr = start_single_file_http_server(server_port, output_file, compressed_file)
        print(get_single_file_http_server_help(server_port))
        if args.run:
            run_command([args.browser, "http://localhost:%i" % (server_port)])
    elif args.run:
        # Execute browser if necessary.
        run_command([args.browser, str(output_file)])

    sys.exit(0)

########################################
# Entry point ##########################
########################################

if __name__ == "__main__":
    sys.exit(main())
