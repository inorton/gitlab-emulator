import os.path

import yaml

class DocumentList(list):
    def flatten(self) -> list:
        resolved = []
        for item in self:
            if isinstance(item, DocumentList):
                resolved.extend(item.flatten())
            else:
                resolved.append(item)
        return resolved


class BambooYamlLoader(yaml.FullLoader):
    def __init__(self, stream, filename):
        super(BambooYamlLoader, self).__init__(stream)
        self.filename = filename
        self.add_constructor(u"!include", include_constructor)


def include_constructor(loader: BambooYamlLoader, node):
    folder = os.path.dirname(loader.filename)
    newfile = os.path.join(folder, node.value)
    with open(newfile, "r") as data:
        docs = yaml.load_all(data, get_stream_loader(newfile))
        return DocumentList([x for x in docs])


def get_stream_loader(filename) -> callable:
    def loader_func(stream):
        return BambooYamlLoader(stream, filename=filename)
    return loader_func
