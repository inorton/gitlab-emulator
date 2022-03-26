"""
Preserve order of keys
"""
import yaml
from collections import OrderedDict
from yaml.resolver import BaseResolver


def reference_constructor(loader, node):
    address = []
    for item in node.value:
        address.append(item.value)

    jobname = address[0]
    jobelement = address[1]
    elementvalue = None
    if len(address) > 2:
        elementvalue = address[2]
    return {
        "!reference": {
            "job": jobname,
            "element": jobelement,
            "value": elementvalue
        }
    }


yaml.add_constructor(u"!reference", reference_constructor)


def ordered_load(stream, Loader=yaml.SafeLoader):
    class OrderedLoader(Loader):
        pass

    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return OrderedDict(loader.construct_pairs(node))

    OrderedLoader.add_constructor(BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    return yaml.load(stream, OrderedLoader)
