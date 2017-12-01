#!/usr/bin/env python

import os
import logging
import logging.handlers
import json
import time
import ConfigParser
from collections import defaultdict
try:
    from oddmon import lfs_utils
except:
    import lfs_utils

logger = None        # used for normal logging messages
stats_logger = None  # the logger we use to write the stats data


# A class used simply as a place to store globals (and in particular, the C
# equivalent of static globals). Don't instantiate individual 'G' objects.
class G:
    # attributes used by the subscriber
    stats = defaultdict(lambda: defaultdict(int))
    buf = None
    save_dir = None

    # attributes used by the publisher
    fsname = ''
    target_names = []
    # Holds the names of the OST or MDT target(s) that the server we're
    # running on manages.

    job_times = defaultdict(lambda: defaultdict(int))
    # A dict of dicts of the most recent job id's & timestamps.  (Note:
    # calling int() returns 0, which is useful since that's what we want for
    # our default timstamps.) Used down in read_target_stats() to ensure we
    # don't repeat data that hasn't changed since the previous check.
    # ex: G.job_times[<OST Name>][<job ID>] = <timestamp>

    is_mds = True  # We handle the MDS a little differently from the OSS's

    # attributes used by both subscriber & publisher
    # None yet...


def metric_init(name, config_file, is_subscriber=False,
                loglevel=logging.DEBUG):
    global logger, stats_logger
    logger = logging.getLogger("app.%s" % __name__)

    rv = True
    if is_subscriber is False:
        G.fsname, G.target_names = lfs_utils.scan_targets(OSS=False)
        if not G.target_names:
            # Check if we're running on an OSS
            G.is_mds = False
            G.fsname, G.target_names = lfs_utils.scan_targets(OSS=True)
            if not G.target_names:
                logger.warn("No OST's or MDT's found.  Disabling plugin.")
                rv = False
            elif not G.fsname:
                logger.error("OST's found, but could not discern filesystem "
                             "name. (This shouldn't happen.)  Disabling "
                             "plugin.")
                rv = False
        elif not G.fsname:
            logger.error("MDT's found, but could not discern filesystem "
                         "name. (This shouldn't happen.)  Disabling "
                         "plugin.")
            rv = False
          
    else:
        # config file is only needed for the location of the
        # stats_logger file, and that's only needed on the
        # subscriber side
        config = ConfigParser.SafeConfigParser()
        try:
            config.read(config_file)
            G.save_dir = config.get(name, "save_dir")

            # log to file until reaching maxBytes then create a new log file
            stats_logger = logging.getLogger("brw_stats.%s" % __name__)
            stats_logger.propagate = False
            stats_logger_name = G.save_dir+os.sep+"job_log.txt"
            logger.debug("Stats data saved to: %s" % stats_logger_name)
            stats_logger.addHandler(
                logging.handlers.RotatingFileHandler(stats_logger_name,
                                                     maxBytes=1024*1024*1024,
                                                     backupCount=1))
            stats_logger.setLevel(logging.DEBUG)
        except Exception, e:
            logger.error("Can't read configuration file")
            logger.error("Exception: %s" % e)
            rv = False

    return rv


def metric_cleanup(is_subscriber=False):
    pass


def get_stats():
    if G.fsname is None:
        logger.error("No valid file system...skip")
        return ""

    update()

    return json.dumps(G.stats)


def save_stats(msg):
    stats = json.loads(msg)
    # msg (and thus stats) is organized as a dictionary with target (OST or
    # MDT) names for keys.  The associated values are themselves lists of
    # dictionaries where each dictionary is the key/value data for one job.

    for target in stats.keys():
        jobList = stats[target]
        for job in jobList:
            # convert the python structure into an event string suitable
            # for Splunk and write it out
            # Note that the formats for the OST's and MDT's differ
            if 'mknod:' in job:  # Is this an MDT record?
                event_str = "ts=%d job_id=%s open=%d  close=%d " %\
                            (int(job["snapshot_time:"]), str(job["job_id:"]),
                             int(job["open:"]), int(job["close:"]))
                event_str += "mknod=%d link=%d unlink=%d mkdir=%d " %\
                             (int(job["mknod:"]), int(job["link:"]),
                              int(job["unlink:"]), int(job["mkdir:"]))
                event_str += "rmdir=%d rename=%d getattr=%d setattr=%d " %\
                             (int(job["rmdir:"]), int(job["rename:"]),
                              int(job["getattr:"]), int(job["setattr:"]))
                event_str += "getxattr=%d setxattr=%d statfs=%d sync=%d " %\
                             (int(job["getxattr:"]), int(job["setxattr:"]),
                              int(job["statfs:"]), int(job["sync:"]))
                event_str += "samedir_rename=%d crossdir_rename=%d MDS=%s" %\
                             (int(job["samedir_rename:"]),
                              int(job["crossdir_rename:"]), str(target))
            else:  # OST record
                event_str = "ts=%d job_id=%s write_samples=%d " %\
                            (int(job["snapshot_time:"]), str(job["job_id:"]),
                             int(job["write_samples:"]))
                event_str += "write_sum=%d read_samples=%d read_sum=%d " %\
                             (int(job["write_sum:"]),
                              int(job["read_samples:"]),
                              int(job["read_sum:"]))
                event_str += "punch=%d setattr=%d sync=%d OST=%s" %\
                             (int(job["punch:"]), int(job["setattr:"]),
                              int(job["sync:"]), str(target))

            stats_logger.info(event_str)


def update():
    if G.is_mds:
        base_path = '/proc/fs/lustre/mdt/'
    else:
        base_path = '/proc/fs/lustre/obdfilter/'

    for target in G.target_names:
        fpath = base_path + target
        ret = read_target_stats(fpath, target)
        if ret:
            G.stats[target] = ret
        else:
            # The only time we'd get here is if read_target_stats() hit an
            # error and exited early...which it wouldn't do without raising
            # an exception.
            G.stats[target] = []


def read_target_stats(path, target_name):
    stats = []  # The return value - a list of dictionaries where each
                # dictionary holds key/value pairs for a single job

    pfile = os.path.realpath(path) + "/job_stats"

    with open(pfile) as f:
        flag = True
        timestamp = int(time.time())

        # The OST's and MDT's have different data in their job_stats files
        if G.is_mds:
            kw = ["open:", "close:", "mknod:", "link:", "unlink:", "mkdir:",
                  "rmdir:", "rename:", "getattr:", "setattr:", "getxattr:",
                  "setxattr:", "statfs:", "sync:", "samedir_rename:",
                  "crossdir_rename:"]
            stanza_lines = 18
            data_elements = 18
        else:
            kw = ["punch:", "setattr:", "sync:"]
            stanza_lines = 7
            data_elements = 9  # 2 of the lines have 2 elements each

        job_times = defaultdict(int)  # holds job ids & timestamps.
                                      # Compare against G.job_times[<target_name>]
        next(f)  # ignore the first line (it just says "job stats:")
        while flag:
            job = {}  # stores key/value pairs for a single job in the file

            # Each pass through this inside while loop should parse
            # a single complete stanza
            i = 1
            while i % (stanza_lines + 1) != 0:
                try:
                    data = next(f)
                except:
                    flag = False
                    if i != 1:
                        logger.error("job_stats file ended with an "
                                     "incomplete job stanza.  That "
                                     "shouldn't happen.")
                    break
                line = data.split()
                # There's some lines in the stanza that are special cases
                if "job_id:" in line:
                    job["job_id:"] = line[2]
                elif "snapshot_time:" in line:
                    job["snapshot_time:"] = line[1]
                elif "read:" in line:
                    job["read_sum:"] = line[11]
                    job["read_samples:"] = line[3].strip(",")
                elif "write:" in line:
                    job["write_sum:"] = line[11]
                    job["write_samples:"] = line[3].strip(",")

                # all the other lines are handled with the keyword lists
                elif any(s in line for s in kw):
                    job[line[0]] = line[3].strip(",")

                else:  # sanity check
                    logger.warn("Ignoring unexpected line in job_stats file:")
                    logger.warn(data)
                    logger.warn("This shouldn't happen.  Has Lustre"
                                " been updated?")
                i += 1

            if len(job) == data_elements:
                # If we've read a complete job stanza, then check the
                # timestamp: it's possible that nothing has changed since
                # the last time we read this job_id. In that case we're not
                # going to resend the data.
                job_id = job["job_id:"]
                if G.job_times[target_name][job_id] >= \
                   int(job["snapshot_time:"]):
                    # Hooray for defaultdict:  if the time hasn't been set,
                    # it will default to 0

                    # Copy the old timestamp and don't output the data
                    job_times[job_id] = G.job_times[target_name][job_id]
                else:
                    # updated data
                    job_times[job_id] = int(job["snapshot_time:"])
                    # Note the conversion to int!  Want to ensure the
                    # comparison up above works as expected!
                    stats.append(job)
            elif len(job) != 0:
                # A length of 0 means the file ended where it was supposed to.
                # A non-zero length means we somehow got part of a job stanza.
                logger.error("Ignoring incomplete job stanza.  This "
                             "shouldn't happen.")

    # Done reading the job_stats file

    # Replace G.job_stats with job_stats for use the next time we're called
    G.job_times[target_name] = job_times

    return stats
