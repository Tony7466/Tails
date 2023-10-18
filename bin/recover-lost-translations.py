#!/usr/bin/env python3

"""
"""

import git
import polib

import logging
import subprocess
import sys
import pathlib

logger = logging.getLogger(__name__)

OLD_REF = sys.argv[1]
NEW_REF = sys.argv[2]

repo = git.Repo("")
old = repo.commit(OLD_REF)
diff = old.diff(NEW_REF)

logging.basicConfig()

def recover_from_old(e_old, e_new):
    if e_old.fuzzy:
        return False

    if e_new.fuzzy:
        return True

    if not e_new.msgstr:
        return True

    return False

changed = False

git_base = pathlib.Path(repo.git_dir).parent

for i in diff:
    if not i.b_path.endswith(".po"):
        continue
    if i.change_type not in ("R", "M"):
        continue

    a = i
    try:
        pofile_old = polib.pofile(i.a_blob.data_stream.read().decode("utf-8"), encoding="utf-8", wrapwidth=79)
    except OSError as e:
        logger.warning(f"{i.a_path}@{OLD_REF}: {e}")
        continue

    try:
        pofile_new = polib.pofile(i.b_blob.data_stream.read().decode("utf-8"), encoding="utf-8", wrapwidth=79)
    except OSError as e:
        logger.warning(f"{i.b_path}@{NEW_REF}: {e}")
        continue

    changed_file = False

    for e_new in pofile_new:
        e_old = pofile_old.find(e_new.msgid, by="msgid")
        if not e_old:
            continue

        if recover_from_old(e_old, e_new):
            changed_file = True
            e_new.merge(e_old)
            if not e_old.fuzzy and e_new.fuzzy:
                e_new.flags.remove('fuzzy')

    if changed_file:
        newpath = i.b_path
        subprocess.run(['msgconv', '-w', '79', '-t', 'utf-8' ,'-o', str(git_base/newpath)],
                       input=pofile_new.__unicode__().encode('utf-8'),
                       check=True)
        changed = True
