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


def hamming_distance(x, y):
    dist = 0
    val = x ^ y
    while val:
        dist += 1
        val &= val - 1
    return dist


def vhash_match(video1, video2):
    vhash1 = vhash(video1)
    vhash2 = vhash(video2)

    def match_function(a, b):
        return hamming_distance(a, b) < 16  # tolerant minor difference

    return CustomSequenceMatcher(None, vhash1, vhash2, match_function).ratio()


def print_usage():
    print('Usage:')
    print('    {} gen video'.format(os.path.basename(__file__)))
    print('    {} match video1 video2'.format(os.path.basename(__file__)))
    print('    {} matchdir folder'.format(os.path.basename(__file__)))


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
    path1 = None
    path2 = None
    try:
        cmd = sys.argv[1]
        if cmd == 'gen':
            path1 = sys.argv[2]
            if not os.path.isfile(path1):
                raise ValueError('path1 should be an existed file.')
        elif cmd == 'match':
            path1 = sys.argv[2]
            path2 = sys.argv[3]
            if not os.path.isfile(path1):
                raise ValueError('path1 should be an existed file.')
            if not os.path.isfile(path2):
                raise ValueError('path2 should be an existed file.')
        elif cmd == 'matchdir':
            path1 = sys.argv[2]
            if not os.path.isdir(path1):
                raise ValueError('path1 should be an existed folder.')
        else:
            raise ValueError('Unsupported command.')
    except Exception:
        print_usage()
    else:
        if cmd == 'gen':
            print('Processing:\n  {}'.format(path1))
            vhash1 = vhash(path1)
            if vhash1:
                basename, ext = os.path.splitext(path1)
                vhashpath = '{}.vh1'.format(basename)
                if not os.path.exists(vhashpath):
                    print 'Writing video hash to file...'
                    with bz2.BZ2File(vhashpath, 'w') as fout:
                        json.dump(vhash1, fout)
        elif cmd == 'match':
            print('Comparing:\n  {}\n  {}'.format(path1, path2))
            match_ratio = vhash_match(path1, path2)
            print_similarity(match_ratio)
        elif cmd == 'matchdir':
            filelist = glob.iglob(os.path.join(path1, '*.vh1'))
            for file1, file2 in itertools.combinations(filelist, 2):
                print('Comparing:\n  {}\n  {}'.format(file1, file2))
                match_ratio = vhash_match(file1, file2)
                print_similarity(match_ratio)


if __name__ == '__main__':
    # import cProfile as profile
    # profile.run('main()')
    main()
