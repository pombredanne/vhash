#!/usr/bin/env python
import os
import sys
import json
import glob
import ast
import bz2
import itertools

try:
    from gmpy2 import popcount as bit_count
except:
    def bit_count(x):
        dist = 0
        while x:
            dist += 1
            x &= x - 1
        return dist


def vhash(video_path, force=False):
    basename, ext = os.path.splitext(video_path)
    vhashpath = '{}.vh2'.format(basename)
    if os.path.exists(vhashpath):
        print('Getting cached video hash...')
        with open(vhashpath, 'r') as fp:
            result = [int(line, 16) for line in fp]
        return result

    print('Generating video hash...')
    if os.system('./vhash "{0}" "{1}"'.format(video_path, vhashpath)) == 0:
        with open(vhashpath, 'r') as fp:
            result = [int(line, 16) for line in fp]
        return result
    else:
        print('Failed to open file, the file may not be a video.')


def vhash_match(video1, video2):
    vhash1 = vhash(video1)
    vhash2 = vhash(video2)

    scores = [min(bit_count(vh1 ^ vh2) for vh2 in vhash2) for vh1 in vhash1]
    match_ratio = float(sum(s <= 8 for s in scores)) / len(scores)
    return match_ratio


def print_usage():
    print("""Usage:
    {0} gen video ...
    {0} match video_or_folder ...""".format(os.path.basename(__file__)))


def print_similarity(match_ratio):
    if match_ratio > 0.2:
        print('\033[0;31mVery High Similarity: {:.2f}%\033[0m'.format(match_ratio * 100))
    elif match_ratio > 0.1:
        print('\033[0;35mHigh Similarity: {:.2f}%\033[0m'.format(match_ratio * 100))
    elif match_ratio > 0.05:
        print('\033[0;33mMedium Similarity: {:.2f}%\033[0m'.format(match_ratio * 100))
    else:
        print('Low Similarity: {:.2f}%'.format(match_ratio * 100))


def main():
    cmd = None
    target_files = []
    target_folders = []
    try:
        cmd = sys.argv[1]
        target_files = [x for x in sys.argv[2:] if os.path.isfile(x)]
        target_folders = [x for x in sys.argv[2:] if os.path.isdir(x)]
        if cmd not in ('gen', 'match'):
            raise ValueError('Unsupported command.')
    except Exception:
        print_usage()
    else:
        if cmd == 'gen':
            for x in target_files:
                print('Processing:\n  {}'.format(x))
                vhash1 = vhash(x)
                if vhash1:
                    basename, ext = os.path.splitext(x)
                    vhashpath = '{}.vh2'.format(basename)
                    if not os.path.exists(vhashpath):
                        print 'Writing video hash to file...'
                        with bz2.BZ2File(vhashpath, 'w') as fout:
                            json.dump(vhash1, fout)
        elif cmd == 'match':
            for x in target_folders:
                target_files.extend(glob.iglob(os.path.join(x, '*.vh2')))
            print('Start comparing {} files'.format(len(target_files)))
            for file1, file2 in itertools.combinations(target_files, 2):
                print('Comparing:\n  {}\n  {}'.format(file1, file2))
                match_ratio = vhash_match(file1, file2)
                print_similarity(match_ratio)


if __name__ == '__main__':
    # import cProfile as profile
    # profile.run('main()')
    main()
