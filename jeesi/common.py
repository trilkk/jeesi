import subprocess

########################################
# Globals ##############################
########################################

g_verbose = []

########################################
# Functions ############################
########################################

def append_to_path_list(lst, new_path):
    """Appends a path to a path list unless already found."""
    resolved_path = new_path.resolve()
    for ii in lst:
        if ii.resolve() == resolved_path:
            return lst
    return lst + [new_path]

def find_path(starting_path, sub_path_name):
    """Try to find subpath by walking up from path."""
    current_path = starting_path
    while True:
        test_path = current_path / sub_path_name
        if test_path.exists() and test_path.is_dir():
            return test_path
        next_path = current_path.parent
        if next_path == current_path:
            return None
        current_path = next_path

def is_verbose():
    """Tell if verbose mode is on."""
    return (len(g_verbose) > 0) and g_verbose[-1]

def pop_verbose():
    """Pop verbosity status."""
    global g_verbose
    if len(g_verbose) <= 0:
        raise RuntimeError("pop on empty verbosity stack")
    g_verbose.pop()

def push_verbose(op):
    """Push verbosity status."""
    global g_verbose
    g_verbose += [op]

def run_command(lst, decode_output=True):
    """Run program identified by list of command line parameters."""
    if is_verbose():
        print("Executing command: %s" % (" ".join(lst)))
    proc = subprocess.Popen(lst, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (proc_stdout, proc_stderr) = proc.communicate()
    if decode_output and not isinstance(proc_stdout, str):
        proc_stdout = proc_stdout.decode()
    if decode_output and not isinstance(proc_stderr, str):
        proc_stderr = proc_stderr.decode()
    returncode = proc.returncode
    if 0 != proc.returncode:
        raise RuntimeError("command failed: %i, stderr output:\n%s" % (proc.returncode, proc_stderr))
    return (proc_stdout, proc_stderr)
