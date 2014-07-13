#!/usr/bin/env python
import os
import sys
import json
import glob
import ast
import bz2
import itertools
import cv2
from difflib2 import CustomSequenceMatcher

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
    vhashpath = '{}.vh1'.format(basename)
    if os.path.exists(vhashpath):
        print('Getting cached video hash...')
        return json.load(bz2.BZ2File(vhashpath))

    print('Generating video hash...')
    cap = cv2.VideoCapture(video_path)
    if cap.isOpened():
        fps = int(cap.get(cv2.cv.CV_CAP_PROP_FPS))
        result = []
        i = 0
        retval = cap.grab()
        while retval:
            if i % fps == 0:
                _, image = cap.retrieve()
                image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                image = cv2.resize(image, (8, 8))
                pixels = [image[y, x] for y in xrange(8) for x in xrange(8)]
                avg_pixel = sum(pixels) / len(pixels)
                bits = [('0' if p > avg_pixel else '1') for p in pixels]
                val = ast.literal_eval('0b' + ''.join(bits))
                result.append(val)
            retval = cap.grab()
            i += 1
        cap.release()
        if result:
            return result
    else:
        print('Failed to open file, the file may not be a video.')


def vhash_match(video1, video2):
    vhash1 = vhash(video1)
    vhash2 = vhash(video2)

    def match_function(a, b):
        return bit_count(a ^ b) <= 8  # tolerant minor difference

    return CustomSequenceMatcher(None, vhash1, vhash2, match_function).ratio()


def print_usage():
    print("""Usage:
    {0} gen video ...
    {0} match video_or_folder ...""".format(os.path.basename(__file__)))


def print_similarity(match_ratio):
    if match_ratio > 0.2:
        print('Very High Similarity: {:.2f}%'.format(match_ratio * 100))
    elif match_ratio > 0.1:
        print('High Similarity: {:.2f}%'.format(match_ratio * 100))
    elif match_ratio > 0.05:
        print('Medium Similarity: {:.2f}%'.format(match_ratio * 100))
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
                    vhashpath = '{}.vh1'.format(basename)
                    if not os.path.exists(vhashpath):
                        print 'Writing video hash to file...'
                        with bz2.BZ2File(vhashpath, 'w') as fout:
                            json.dump(vhash1, fout)
        elif cmd == 'match':
            for x in target_folders:
                target_files.extend(glob.iglob(os.path.join(x, '*.vh1')))
            print('Start comparing {} files'.format(len(target_files)))
            for file1, file2 in itertools.combinations(target_files, 2):
                print('Comparing:\n  {}\n  {}'.format(file1, file2))
                match_ratio = vhash_match(file1, file2)
                print_similarity(match_ratio)


if __name__ == '__main__':
    # import cProfile as profile
    # profile.run('main()')
    main()
