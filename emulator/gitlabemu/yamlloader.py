"""
Preserve order of keys
"""
import yaml
from collections import OrderedDict
from yaml.resolver import BaseResolver


def ordered_load(stream, Loader=yaml.SafeLoader):
    class OrderedLoader(Loader):
        pass

    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return OrderedDict(loader.construct_pairs(node))

    OrderedLoader.add_constructor(BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    return yaml.load(stream, OrderedLoader)
