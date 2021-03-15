import os
import random

os.makedirs("generated")

tag = "dynamic-{}".format(random.randint(1, 99))

print("Using dynamic tag: {}".format(tag))

with open(
        os.path.join("children", "child-pipeline.yml"), "r") as cf:
    content = cf.read()

with open(os.path.join("generated", "child-pipeline.yml"), "w") as cf:
    cf.write(content.replace("DYNAMIC_TAG", tag))

with open(os.path.join("generated", "child-tag.txt"), "w") as cf:
    cf.write(tag)
