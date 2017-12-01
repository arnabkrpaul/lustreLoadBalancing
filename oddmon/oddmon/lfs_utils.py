#!/usr/bin/env python

import os
import glob
import logging

class G:
    fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

def scan_targets( OSS=True):
    fsname = None
    targetnames = []
    targets = []
    
    if OSS:
        targets = glob.glob("/proc/fs/lustre/obdfilter/*OST*")
    else:
        targets = glob.glob("/proc/fs/lustre/mdt/*MDT*")
        
    if len(targets) != 0:
        fsname, _ = os.path.basename(targets[0]).split("-")
        for target in targets:
            targetnames.append(os.path.basename(target))
    return fsname, targetnames

def get_filehandler(f, m="w", level=logging.DEBUG):
    fh = logging.FileHandler(filename=f, mode=m)
    fh.setLevel(level)
    fh.setFormatter(G.fmt)
    return fh

def get_consolehandler(level=logging.DEBUG):
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(G.fmt)
    return ch



