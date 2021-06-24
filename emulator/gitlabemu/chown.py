#!/usr/bin/env python3
import os
# change the owner and group of files within the current working directory if they do not match

SET_UID = int(os.getenv("CHOWN", "0"))
SET_GID = int(os.getenv("CHGRP", "0"))
changed = 0

print(f"Restoring uid/gid to {SET_UID}:{SET_GID} in {os.getcwd()} ..")

for root, folders, files in os.walk(os.getcwd()):
    for item in folders + files:
        path = os.path.join(root, item)
        relpath = os.path.relpath(path, os.getcwd())
        if os.path.exists(path):
            st = os.stat(path)
            if st.st_uid != SET_UID or st.st_gid != SET_GID:
                try:
                    os.chown(path, SET_UID, SET_GID)
                    changed += 1
                except Exception as err:
                    print(f"Warning: Could not restore uid/gid on {relpath} : {err}")

print(f"Restored ownership of {changed} files/folders")
