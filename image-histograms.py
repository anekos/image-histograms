#!/usr/bin/env python
# https://stackoverflow.com/questions/30698004/how-can-i-serialize-a-numpy-array-while-preserving-matrix-dimensions

import cv2
import math
import os
import pickle
import sqlite3
from sys import argv, stderr



IMAGE_SIZE = (200, 200)
DB_PATH = os.path.expanduser('~/.cache/image-histogram.sqlite')
INSERT_SQL = 'INSERT INTO histograms (path, width, height, histogram) VALUES (?, ?, ?, ?)'



conn = sqlite3.connect(DB_PATH)


class Entry:
    def __init__(self, path, width, height, histogram):
        self.path = path
        self.width = width
        self.height = height
        self.histogram = histogram



def init():
    conn.execute('CREATE TABLE IF NOT EXISTS histograms (path TEXT NOT NULL PRIMARY KEY, width INTEGER, height INTEGER, histogram TEXT NOT NULL)');



def fetch_all():
    cur = conn.cursor()
    cur.execute(u"select path, width, height, histogram from histograms")
    result = {}
    for rows in cur:
        path, width, height, histogram = rows
        result[path] = Entry(path, width, height, histogram)
    return result



def calc_hist(image_path):
    image = cv2.imread(image_path)
    image = cv2.resize(image, IMAGE_SIZE)
    return cv2.calcHist([image], [0], None, [256], [0, 256])



def collect_file(image_path):
    histogram = calc_hist(image_path)
    serialized = pickle.dumps(histogram, protocol=0)
    width, height = IMAGE_SIZE
    conn.execute(INSERT_SQL, (image_path, width, height, serialized))



def collect(directory_path):
    current = fetch_all()

    targets = []
    for (root, _, files) in os.walk(directory_path):
        for file in files:
            path = os.path.join(root, file)

            if not os.path.isfile(path): continue

            if path in current: continue

            _, ext = os.path.splitext(path)
            if not ext in ('.png', '.jpeg', '.jpg'): continue

            targets.append(path)

    total = len(targets)

    for (index, path) in enumerate(targets):
        try:
            collect_file(path)
            print('%d/%d\t%s' % (index + 1, total, path))
        except:
            print >> stderr, 'ERROR: %d/%d\t%s' % (index + 1, total, path)

    conn.commit()



def search(image_path):
    current = fetch_all()

    target_hist = calc_hist(image_path)

    for entry in current.values():
        histogram = pickle.loads(entry.histogram)
        ratio = cv2.compareHist(target_hist, histogram, 0)
        if 0.9999 < abs(ratio) and entry.path != image_path:
            print('@push-image --force --meta DUPE_RATIO=%f %s' % (ratio, entry.path))

    if not image_path in current:
        serialized = pickle.dumps(target_hist, protocol=0)
        width, height = IMAGE_SIZE
        conn.execute(INSERT_SQL, (image_path, width, height, serialized))
        conn.commit()



def check():
    current = fetch_all()
    total = len(current) - 1
    total = total * math.ceil(total / 2)
    now = 0

    for (index_out, entry_out) in enumerate(current.values()):
        hist_out = pickle.loads(entry_out.histogram)
        first = True

        founds = 0
        for (index_in, entry_in) in enumerate(current.values()):
            if index_in <= index_out: continue

            now += 1
            if now % 100 == 0:
                stderr.write("[2K\r%d%% (%d of %d)" % (now * 100 / total, now, total))

            hist_in = pickle.loads(entry_in.histogram)
            ratio = cv2.compareHist(hist_in, hist_out, 0)

            if 0.9999 < abs(ratio):
                stderr.write("\n")
                founds += 1
                if first:
                    print('@push-image --force --meta DUPE_RATIO=%f --meta INDEX=%d %s' % (ratio, 0, entry_out.path))
                    first = False
                print('@push-image --force --meta DUPE_RATIO=%f --meta INDEX=%d %s' % (ratio, founds, entry_in.path))

    stderr.write("[2K\r%d%% (%d of %d)" % (100, now, total))



def main(command, args):
    init()
    if command == 'search':
        search(args[0])
    elif command == 'collect':
        collect(args[0])
    elif command == 'check':
        check()



if __name__ == '__main__':
    main(argv[1], argv[2:])
