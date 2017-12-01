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
    mdtnames = None
    stats = defaultdict(lambda: defaultdict(int))


def metric_init(name, config_file, is_subscriber=True,
                loglevel=logging.DEBUG):
    global logger, stats_logger
    logger = logging.getLogger("app.%s" % __name__)
    rv = True

    if is_subscriber is False:
        G.fsname, G.mdtnames = lfs_utils.scan_targets(OSS=False)
        if not G.mdtnames:
                logger.warn("No MDT's found.  Disabling plugin.")
                rv = False
        elif not G.fsname:
                logger.error("MDT's found, but could not discern filesystem name. "
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
        stats_logger = logging.getLogger("mds_lnet_stats.%s" % __name__)
        stats_logger.propagate = False
        stats_logger_name = G.save_dir+os.sep+"mds_lnet_stats_log.txt"
        logger.debug("Stats data saved to: %s" % stats_logger_name)
        stats_logger.addHandler(
            logging.handlers.RotatingFileHandler(stats_logger_name,
                                                 maxBytes=1024*1024*1024,
                                                 backupCount=1))
        stats_logger.setLevel(logging.DEBUG)




    return rv


def metric_cleanup(is_subscriber=True):
    pass


def get_stats():

    if G.fsname is None:
        logger.error("No valid file system ... skip")
        return ""

    update()

    return json.dumps(G.stats)


def save_stats(msg):
    stats = json.loads(msg)

    event_str = "send_count=%f  send_length=%f recv_length=%f recv_count=%f snapshot=%d" %\
                 (float(stats["send_count"]), float(stats["send_length"]) ,float(stats["recv_length"]), float(stats["recv_count"]), int(time.time()))
    stats_logger.info(event_str)




def read_lnet_stats(f):
    """
    expect input of a path to lnet stats
    return a dictionary with key/val pairs
    """
    ret = {'send_count': 0, 'recv_count': 0, 'send_length':0, 'recv_length': 0}

    pfile = os.path.normpath(f) + "/stats"
    with open(pfile, "r") as f:
            for line in f:
                chopped = line.split()
                if chopped[3]:
                    ret["send_count"] = int(chopped[3])
                if chopped[4]:
                    ret["recv_count"] = int(chopped[4])
                if chopped[7]:
                    ret["send_length"] = int(chopped[7])
                if chopped[8]:
                    ret["recv_length"] = int(chopped[8])


    if ret['send_count'] == 0 and ret['recv_count'] == 0 and ret['send_length'] == 0 and ret['recv_length'] == 0 :
        return None

    return ret


def update():

        fpath = '/proc/sys/lnet'
        ret = read_lnet_stats(fpath)
        if ret:
            G.stats = ret

if __name__ == '__main__':
    metric_init("mds-lnet-stats")
    while True:
        print get_stats()
        time.sleep(5)
    metric_cleanup()
