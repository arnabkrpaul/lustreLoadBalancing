#!/usr/bin/env python

import os
import ConfigParser
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
    save_dir = None


def metric_init(name, config_file, is_subscriber=False,
                loglevel=logging.DEBUG):
    global logger, stats_logger
    logger = logging.getLogger("app.%s" % __name__)
    rv = True

    G.fsname, G.ostnames = lfs_utils.scan_targets(OSS=True)
    if is_subscriber is False:
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
        stats_logger = logging.getLogger("ost_stats.%s" % __name__)
        stats_logger.propagate = False
        stats_logger_name = G.save_dir+os.sep+"ost_log.txt"
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
        stats_logger.info(stats)
        for target in stats.keys():
                jobList = stats[target]
                # convert the python structure into an event string suitable
                # for Splunk and write it out
                event_str = "ts=%f write_bytes=%f read_bytes=%f " %\
                                    (float(jobList["snapshot_time"]), float(jobList["write_bytes_sum"]),
                                        float(jobList["read_bytes_sum"]))
                event_str += "kbytes_avail=%d OSS=%s" %\
                                     (int(jobList["kbytes_avail"]), str(target))
                stats_logger.info(event_str)



def read_ost_stats(f):
    """
    expect input of a path to ost stats
    return a dictionary with key/val pairs
    """
    ret = {'read_bytes_sum': 0, 'write_bytes_sum': 0}
    f1 = f
    pfile = os.path.normpath(f) + "/stats"
    with open(pfile, "r") as f:
             for line in f:
                chopped = line.split()
                if chopped[0] == "snapshot_time":
                    ret["snapshot_time"] = chopped[1]
                if chopped[0] == "write_bytes":
                    ret["write_bytes_sum"] = int(chopped[6])
                if chopped[0] == "read_bytes":
                    ret["read_bytes_sum"] = int(chopped[6])

    pfile = os.path.normpath(f1) + "/kbytesavail"
    with open(pfile, "r") as f1:
             for line in f1:
                        ret["kbytes_avail"] = int(line)

    if ret['read_bytes_sum'] == 0 and ret['write_bytes_sum'] == 0:
        return None

    return ret




def update():

    for ost in G.ostnames:
        fpath = '/proc/fs/lustre/obdfilter/' + ost
        ret = read_ost_stats(fpath)
        if ret:
            G.stats[ost] = ret


if __name__ == '__main__':
    metric_init("ost-stats")
    while True:
        print get_stats()
        time.sleep(5)
    metric_cleanup()
