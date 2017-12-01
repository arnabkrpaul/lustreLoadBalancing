#!/usr/bin/env python

import os
import ConfigParser
import subprocess
import logging
import json
import time
from collections import defaultdict
try:
    from oddmon import lfs_utils
except:
    import lfs_utils

logger = None


class G:
    fsname = None
    ostnames = None
    stats = defaultdict(lambda: defaultdict(int))


def metric_init(name, config_file, is_subscriber=False,
                loglevel=logging.DEBUG):
    global logger, stats_logger
    logger = logging.getLogger("app.%s" % __name__)
    rv = True

    if is_subscriber is False:
        G.fsname, G.ostnames = lfs_utils.scan_targets(OSS=True)
        if not G.ostnames:
                logger.warn("No OST's found.  Disabling plugin.")
                rv = False
        elif not G.fsname:
                logger.error("OST's found, but could not discern filesystem name. "
                             "(This shouldn't happen.)  Disabling plugin.")
                rv = False

    else:
        # config file is only needed for the location of the
        # stats_logger file, and that's only needed on the
        # subscriber side
        config = ConfigParser.SafeConfigParser()
        try:
            config.read(config_file)
            G.save_dir = config.get(name, "save_dir")
        except Exception, e:
            logger.error("Can't read configuration file")
            logger.error("Exception: %s" % e)
            rv = False

        # TODO: this code block should probably be inside the exception handler
        # log to file until reaching maxBytes then create a new log file
        stats_logger = logging.getLogger("oss_stats.%s" % __name__)
        stats_logger.propagate = False
        stats_logger_name = G.save_dir+os.sep+"oss_stats_log.txt"
        logger.debug("Stats data saved to: %s" % stats_logger_name)
        stats_logger.addHandler(
            logging.handlers.RotatingFileHandler(stats_logger_name,
                                                 maxBytes=1024*1024*1024,
                                                 backupCount=1))
        stats_logger.setLevel(logging.DEBUG)

    return rv

def metric_cleanup(is_subscriber=False):
    pass


def get_stats():

    if G.fsname is None:
        logger.error("No valid file system ... skip")
        return ""

    update()

    return json.dumps(G.stats)


def save_stats(msg):
    stats = json.loads(msg)
    event_str = "cpu=%f  mem=%f snapshot=%d" %\
                 (float(stats["cpu"]), float(stats["mem"]) ,int(time.time()))
    stats_logger.info(event_str)

def read_oss_stats():
    ret = {'cpu': 0, 'mem': 0}
    count=1
    pfile = "/proc/meminfo"
    with open(pfile,"r") as f:
        for line in f:
                chopped = line.split()
                if chopped[0] == "MemTotal:" :
                        mem_tot = float( chopped[1])
                if chopped[0] == "MemFree:" :
                        mem_free = float( chopped[1])

    ret["mem"] = ((mem_tot - mem_free) * 100)/ mem_tot
    pfile = "/proc/loadavg"
    with open(pfile,"r") as f:
        for line in f:
                chopped = line.split()
                if chopped[0]:
                        ret["cpu_avg"] = chopped[0]
    return ret

def update():


        ret = read_oss_stats()
        if ret:
            G.stats = ret

if __name__ == '__main__':
    metric_init("oss-stats")
    while True:
        print get_stats()
        time.sleep(5)
    metric_cleanup()
