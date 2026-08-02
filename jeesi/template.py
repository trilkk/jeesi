import re

from jeesi.common import is_verbose

########################################
# Template #############################
########################################

class Template:
    """Class for templated string generation."""

    def __init__(self, content):
        """Constructor."""
        self.__content = content

    def format(self, substitutions=None):
        """Return formatted output."""
        ret = self.__content
        total_substitutions = 0
        missing_substitutions = []
        if substitutions:
            for kk in substitutions:
                vv = substitutions[kk].replace("\\", "\\\\")
                (ret, num) = re.subn(r'\[\[\s*%s\s*\]\]' % (kk), vv, ret)
                total_substitutions += num
                if not num:
                    missing_substitutions += [kk]
        if substitutions and (total_substitutions <= 0):
            print("WARNING: no substitutions done, tried: %s" % (missing_substitutions))
        unmatched = list(set(re.findall(r'\[\[([^\]]+)\]\]', ret)))
        (ret, num) = re.subn(r'\[\[[^\]]+\]\]', "", ret)
        if num and is_verbose():
            print("Template substitutions not matched: %s (%i)" % (str(unmatched), num))
        return ret

    def __str__(self):
        """String representation."""
        return self.__content
