#!/usr/bin/env python

import os
import logging
import logging.handlers
import ConfigParser
import json
import time
from collections import defaultdict
try:
    from oddmon import lfs_utils
except:
    import lfs_utils

# Globals
logger = None        # used for normal logging messages
stats_logger = None  # the logger we use to write the stats data


class G:
    fsname = None
    ostnames = None
    buf = None
    save_dir = None


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
            logger.error("OST's found, but could not discern filesystem "
                         "name. (This shouldn't happen.)  Disabling plugin.")
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
        stats_logger = logging.getLogger("brw_stats.%s" % __name__)
        stats_logger.propagate = False
        stats_logger_name = G.save_dir+os.sep+"brw_log.txt"
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

    return json.dumps(update())


# A clever way to implement the equivalent of C static variables
def static_vars(**kwargs):
    def decorate(func):
        for k in kwargs:
            setattr(func, k, kwargs[k])
        return func
    return decorate


@static_vars(previous_stats={})
def save_stats(msg):
    logger.debug("Inside save_stats()")
    brw_stats = json.loads(msg)

    for ost in brw_stats.keys():
        logger.debug("save_stats() processing OST '%s'" % ost)
        if not ost in save_stats.previous_stats:
            # The first time through, initialize our static variable then
            # return because we don't have enough data to calculate the diffs
            save_stats.previous_stats[ost] = brw_stats[ost]
            logger.debug("No previous_stats entry for OST '%s'." % ost +
                         "  Skipping remainder of save_stats()")
            continue

        metrics_dict = brw_stats[ost]
        snapshot_time = int(float(metrics_dict["snapshot_time"]))
        # Note: the time value is actually has 6 digits to the right of
        # the decimal point, but we don't need anything more accurate than
        # integer seconds. (Interestingly, Python requires us to convert it
        # to a float first, before truncating it.)

        for metric in metrics_dict.keys():
            if metric == "snapshot_time":
                continue  # snapshot_time is not a metric in and of itself
            else:
                value = metrics_dict[metric]
                logger.debug("%s :: %s" % (metric, value))
                for k in value.keys():
                    # The value we write to Splunk is the difference between
                    # the current counts and the previous counts
                    try:
                        read_prev_counts = int(
                            save_stats.previous_stats[ost][metric][k][0])
                        write_prev_counts = int(
                            save_stats.previous_stats[ost][metric][k][3])
                        # See read_brw_stats() and extract_hist() for how
                        # the publisher formats this data
                    except KeyError, e:
                        # Individual rows in the brw_stats file will come and
                        # go depending on whether there was (for example) any
                        # 256K writes recently.  Basically, it looks like the
                        # Lustre devs tried not to to include rows with 0
                        # counts.
                        logger.debug("KeyError: %s" % e)
                        logger.debug("OST: %s  Metric: %s  k: %s" %
                                     (ost, metric, k))

                        if not metric in save_stats.previous_stats[ost]:
                            save_stats.previous_stats[ost][metric] = {}
                        save_stats.previous_stats[ost][metric][k] = \
                            [u'0', u'0', u'0', u'0', u'0', u'0']
                        read_prev_counts = 0
                        write_prev_counts = 0

                    read_count_delta = int(value[k][0]) - read_prev_counts
                    write_count_delta = int(value[k][3]) - write_prev_counts
                    dbg_str = "metric %s, bucket %s:  read_prev_counts: %d" %\
                              (metric, k, read_prev_counts)
                    dbg_str += "  read_counts: %d write_prev_counts: %d" %\
                               (int(value[k][0]), write_prev_counts)
                    dbg_str += "  write_counts: %d" % (int(value[k][3]))
                    logger.debug(dbg_str)

                    event_str = "ts=%d bucket=%s rc_delta=%s" %\
                                (snapshot_time, k, read_count_delta)
                    event_str += " read_count=%s wc_delta=%s" %\
                                 (value[k][0], write_count_delta)
                    event_str += " write_count=%s" % value[k][3]
                    stats_logger.info("%s OST=%s datatype=%s",
                                      event_str, str(ost), str(metric))

            # end of for metric in metrics_dict.keys()...
        save_stats.previous_stats[ost] = metrics_dict
        # end of for ost in brw_stats.keys()...


def extract_snaptime(ret):
    idx = G.buf.index('\n')
    ret['snapshot_time'] = G.buf[0].split()[1]
    # update buffer
    G.buf = G.buf[idx+1:]


def extract_hist(key, ret):
    idx = None

    try:
        idx = G.buf.index('\n')
    except:
        # We hit this exception when there's no blank line in G.buf (which
        # happens when we're parsing the last block of lines)
        idx = len(G.buf)

    # skip #0 and #1
    # process 1 line at a time
    for line in G.buf[2:idx]:
        fields = line.split()

        # after split: ['128:', '0', '0', '0', '|', '2', '0', '0']
        # first field '128:', remove colon
        ret[key][fields[0][:-1]] = fields[1:4] + fields[5:]

    # update buffer
    G.buf = G.buf[idx+1:]


def read_brw_stats(f):
    """
    expect input of a path to brw stats eg.
    /proc/fs/lustre/obdfilter/mytest-OST0000/brw_stats

    return a dictionary with key/val pairs
    """

    ret = {"snapshot_time"        : '',
           "pages_per_bulk"       : defaultdict(list),
           "discontiguous_pages"  : {},
           "discontiguous_blocks" : {},
           "disk_fragmented_io"   : {},
           "disk_io_in_flight"    : {},
           "io_time"              : {},
           "io_size"              : {}}

    pfile = os.path.realpath(f) + "/brw_stats"
    with open(pfile, "r") as f:
        G.buf = f.readlines()
        extract_snaptime(ret)
        extract_hist('pages_per_bulk',       ret)
        extract_hist('discontiguous_pages',  ret)
        extract_hist('discontiguous_blocks', ret)
        extract_hist('disk_fragmented_io',   ret)
        extract_hist('disk_io_in_flight',    ret)
        extract_hist('io_time',              ret)
        extract_hist('io_size',              ret)

    # trim
    for key in ret.keys():
        if len(ret[key]) == 0:
            del ret[key]

    if len(ret.keys()) > 1:
        return ret
    else:                   # if only snapshot_time, return None
        return None


def update():
    stats = {}
    for ost in G.ostnames:
        fpath = '/proc/fs/lustre/obdfilter/' + ost
        ret = read_brw_stats(fpath)
        if ret:
            stats[ost] = ret
    return stats


if __name__ == '__main__':
    # Set up a basic logging handler to use
    # logging.getLogger("main.__main__").addHandler(logging.StreamHandler())
    metric_init("brw-stats")
    while True:
        print get_stats()
        time.sleep(5)
    metric_cleanup()
