"""Type validators"""

from argparse import ArgumentTypeError


class NameValuePair:
    def __init__(self, text: str):
        params = text.split("=")
        if len(params) == 2:
            self.name = params[0]
            self.value = params[1]
        else:
            raise ArgumentTypeError(f"expected X=Y")


class Match(NameValuePair):
    NAMES = ["status", "ref"]

    def __init__(self, text: str):
        super(Match, self).__init__(text)
        if self.name not in self.NAMES:
            raise ArgumentTypeError(f"'{self.name}' is not one of {self.NAMES}")
        if not self.value:
            if self.name == "ref":
                raise ArgumentTypeError(f"you must supply a branch name or tag")
            if self.name == "status":
                raise ArgumentTypeError(f"you must supply a status value")
