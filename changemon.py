#!/usr/bin/env python
# TODO: fix TWO functions having SAME NAME - it's confusing
# TODO: decouple tree difference check from tree comparison function
# TODO: timestamps in monitor mode output
# Idea: cache results for quick rescanning, update cache when modified attrib of a scanned folder changes

DESC="""  changemon.py - Monitor a directory for changes or compare two directories

In the first mode, two directories are compared. In the second mode, a single directory is monitored for changes. The goal is to provide an easy-to-read summary of changes. 
"""

NOTES="""
Flags:

Files and directories belong to one of the added, removed, or changed groups. Additionally, the unchanged and "shared" (in common to both directories, whether changed or not) groups are available, but only in the first mode. The groups to display are specified by flags - a string of any of the characters "acrsu" (the characters correspond to the first letters of the group names) supplied to the --flags option which will also determine the presented order of the groups. By default, ommitting --flags will produce the same result as if --flags "car" had been typed at the command-line..

Examples:

Compare foo_v1 to foo_v2 to show files that were changed, added and removed:
  $ changemon.py ~/projects/foo_v1 ~/projects/foo_v2

Notes:
Changed files are determined by comparing file sizes, and where two files have the same size, a comparison of their md5 checksums is done (unless --skip-checksums is supplied).

"""

import argparse
import functools
import hashlib
import os
import sys
import textwrap
import time


def parse_args():
    ap = argparse.ArgumentParser(description=textwrap.dedent(DESC),
                                 epilog=textwrap.dedent(NOTES),
                                 formatter_class=argparse.RawTextHelpFormatter)

    mode = ap.add_mutually_exclusive_group(required=True)

    ap.add_argument('-f', '--flags',
                    help='specifies file groups to show, see "flags" below',
                    default='car')
    ap.add_argument('-s', '--skip-checksum',
                    help='don\'t checksum, check modification times instead',
                    action='store_const', const=True, default=False)
    mode.add_argument('-c', '--compare',
                    help='compare two directories',
                    nargs=2, metavar='DIR')
    mode.add_argument('-w', '--watch',
                    help='watch a directory continuously for changes',
                    nargs='?', metavar='DIR', default=os.getcwd())
    ap.add_argument('-i', '--interval',
                    help='update interval in seconds for watch mode',
                    metavar='N', type=int, default=10)
    ap.add_argument('-x', '--cutoff',
                    help='amount of files to list for each group before displaying "and N more" in watch mode output',
                    metavar='N', type=int, default=3)

    return ap.parse_args()


def report(err):
    """ Error-reporting function for os.walk() """
    raise err


def checksum(f):
    with open(f, 'rb') as fh:
        contents = fh.read()
    m = hashlib.md5()
    m.update(contents)
    return m.digest()


def get_checksums(tree):
    checksums = {}
    for root, dirs, files in tree:
        for f in files:
            fname = os.path.join(root, f)
            checksums[fname] = checksum(fname)
    return checksums


def differing(files, skip_checksum=False):
    """ Return True when two files differ """

    def comparison(func, file1, file2):
        file1, file2 = map(func, [file1, file2])
        #print "file1: %s, file2: %s, differ: %s" % (file1, file2, return_if(file1 != file2))
        return file1 != file2

    # if sizes differ, it's true that files aren't the same
    if comparison(os.path.getsize, *files):
        return True

    # if sizes don't differ, check md5sums for accuracy
    elif skip_checksum == False:
        return comparison(checksum, *files)

    # or check modification time instead
    elif skip_checksum == True:
        return comparison(os.path.getmtime, *files)


def pretty_compare(results):
    """ Pretty-print for comparison mode """

    def make_group(tup):
        label, seq = tup
        if seq:
            files_string = '\n'.join(seq) + '\n'
        else:
            files_string = ''
        return '{}\n{}\n{}'.format(label, '-' * len(label), files_string)

    print '\n'.join(map(make_group, results))


def pretty_watch(results, cutoff=3):
    """ Pretty-print for watch mode """

    def make_group(tup):
        label, seq = tup
        if len(seq) <= cutoff:
            files_string = ', '.join(seq)
        else:
            files_string = '{} and {} more'.format(', '.join(seq[:cutoff]),
                                                   len(seq[cutoff:]))
        return '{}: {}'.format(label, files_string)

    output = map(make_group, filter(lambda tup: tup[1], results))

    if output: print '\n'.join(output)


def comparison(flags, t1, t2, skip_checksum=False):
    """ Return differences between two trees generated by os.walk() """

    # this function is just really ugly and confusing!

    join, commonprefix = os.path.join, os.path.commonprefix

    def with_sep(s):
        """ Add path separator to end of path string """
        return join(s, '')

    def erase_from(s, sub):
        """ Remove first count of substring from s """
        # is safe because common prefix is guaranteed to be first substring in s
        return s.replace(sub, '', 1)

    def full_listing(t):
        """ Flat list of files and directories of t, with items preceded by root name """
        dir_listing = []
        for root, dirs, files in t:
            dir_listing.extend([join(root, i)
                               for i in files + [with_sep(d) for d in dirs]])
        return dir_listing

    def stripped_listing(root, l):
        """ Flat list of files and directories with root path stripped """
        return [erase_from(s, with_sep(commonprefix([root] + l))) for s in l] 

    root1, root2           =  t1[0][0], t2[0][0]
    before, after          =  full_listing(t1), full_listing(t2)
    before_str, after_str  =  stripped_listing(root1, before), stripped_listing(root2, after)

    added = [p for p in after_str if not p in before_str]

    removed = [p for p in before_str if not p in after_str]
    
    common = [p for p in after_str if not p in added]

    common_with_roots = [(join(root1, p), join(root2, p))
                          for p in common if not p.endswith(os.path.sep)]

    if 'c' in flags or 'u' in flags:
        differingp = functools.partial(differing, skip_checksum=skip_checksum)

        changed = [erase_from(p[0], with_sep(root1))
                   for p in filter(differingp, common_with_roots)]

        unchanged = [p for p in common
                     if not p in changed and not p.endswith(os.path.sep)]

    groups = [('a', 'Added',        added),
              ('c', 'Changed',      changed),
              ('r', 'Removed',      removed),
              ('s', 'Shared',       common),
              ('u', 'Unchanged',    unchanged)]

    results = []
    for f in flags.lower():
        for char, label, data in groups:
            if char == f:
                results += [(label, sorted(data))]
                break

    return results


def monitor(source):
    """ Loop for monitor mode """

    while os.path.exists(args.watch):
        try:
            try:
                cur_state
                first_run = False
            except NameError:
                cur_state = []
                first_run = True

            if first_run: 
                pre_state = list(os.walk(args.watch, followlinks=True, onerror=report))
            else:
                pre_state = cur_state[:]

            if not args.skip_checksum:
                pre_checksums = get_checksums(pre_state)

            time.sleep(args.interval)

            cur_state = list(os.walk(args.watch, followlinks=True, onerror=report))

            if not args.skip_checksum:
                cur_checksums = get_checksums(cur_state)

            if args.flags.find('s') == -1:
                args.flags += 's'

            trees = [pre_state, cur_state]
            compared = comparison(args.flags, *trees, skip_checksum=True)

            ## FUCK! To compare the checksums in this way I have to write similar functionality
            ## already in comparison() AGAIN!

            changed = []
            for i, tup in enumerate(compared[:]):
                label, seq = tup
                if label == "Shared":
                    for fname in seq:
                        key = os.path.join(pre_state[0][0], fname)
                        if key in pre_checksums:
                            if pre_checksums[key] != cur_checksums[key]:
                                changed.append(fname)
                    del compared[i]        
                    break

            for i, tup in enumerate(compared[:]):
                label, seq = tup
                if label == "Changed":
                    compared[i] = ('Changed', changed)
                break

            pretty_watch(compared, cutoff=args.cutoff)
        except KeyboardInterrupt:
            print
            break


if __name__ == '__main__':

    args = parse_args()

    # comparison mode: compare two directories
    if args.compare:
        trees = [list(os.walk(d, followlinks=True, onerror=report))
                 for d in args.compare]
        pretty_compare(comparison(args.flags, *trees, skip_checksum=args.skip_checksum))

    # watch mode: monitor a directory for changes in a continuous loop
    elif args.watch:
        monitor(args.watch)
