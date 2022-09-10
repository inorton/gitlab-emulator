"""Type validators"""

from argparse import ArgumentTypeError


class NameValuePair:
    def __init__(self, text: str):
        self.name = None
        self.value = None
        params = text.split("=")
        if len(params) == 2:
            self.name = params[0]
            self.value = params[1]

        if self.name and self.value:
            return
        raise ArgumentTypeError("expected X=Y")


class Match(NameValuePair):
    NAMES = ["status", "ref"]

    def __init__(self, text: str):
        super(Match, self).__init__(text)
        if self.name not in self.NAMES:
            raise ArgumentTypeError(f"'{self.name}' is not one of {self.NAMES}")


class RefMatch(Match):
    def __init__(self, text: str):
        super(RefMatch, self).__init__(f"ref={text}")
