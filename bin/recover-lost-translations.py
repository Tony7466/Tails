#!/usr/bin/env python3

"""
"""

import git
import polib

import argparse
import logging
import subprocess
import sys
import pathlib


def recover_from_old(e_old, e_new):
    if not e_old.translated():
        return False

    if e_new.translated():
        return False

    return True


def copy(e_to, e_from):
    """
    Copies the content from a given entry to a given entry.
    """
    e_to.msgid = e_from.msgid
    e_to.msgstr = e_from.msgstr
    e_to.occurrences = e_from.occurrences
    e_to.comment = e_from.comment
    e_to.flags = e_from.flags[:]  # clone flags
    e_to.msgid_plural = e_from.msgid_plural
    e_to.obsolete = e_from.obsolete
    if e_from.msgstr_plural:
        for pos in e_from.msgstr_plural:
            try:
                # keep existing translation at pos if any
                e_to.msgstr_plural[pos]
            except KeyError:
                e_to.msgstr_plural[pos] = ''



logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser()
parser.add_argument('--width', '-w', type=int, default=80, help='Width to wrap lines')
parser.add_argument('old_ref', help='commit before the probleatic commit')
parser.add_argument('new_ref', default='HEAD', help='commit onto you recover. normally you want  to use HEAD here.', nargs='?')
args = parser.parse_args()

repo = git.Repo("")
old = repo.commit(args.old_ref)
diff = old.diff(args.new_ref)

logging.basicConfig()




changed = False

git_base = pathlib.Path(repo.git_dir).parent

for i in diff:
    if not i.b_path.endswith(".po"):
        continue
    if i.change_type not in ("R", "M"):
        continue

    a = i
    try:
        pofile_old = polib.pofile(i.a_blob.data_stream.read().decode("utf-8"), encoding="utf-8", wrapwidth=args.width)
    except OSError as e:
        logger.warning(f"{i.a_path}@{args.old_ref}: {e}")
        continue

    try:
        pofile_new = polib.pofile(i.b_blob.data_stream.read().decode("utf-8"), encoding="utf-8", wrapwidth=args.width)
    except OSError as e:
        logger.warning(f"{i.b_path}@{args.new_ref}: {e}")
        continue

    changed_file = False

    for e_new in pofile_new:
        e_old = pofile_old.find(e_new.msgid, by="msgid")
        if not e_old:
            continue

        if recover_from_old(e_old, e_new):
            changed_file = True
            copy(e_new, e_old)

    if changed_file:
        newpath = i.b_path
        subprocess.run(['msgcat', '--width', str(args.width), '-t', 'utf-8' ,'-o', str(git_base/newpath), '-'],
                       input=pofile_new.__unicode__().encode('utf-8'),
                       check=True)
        changed = True
