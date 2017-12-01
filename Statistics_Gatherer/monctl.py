#!/usr/bin/env python
from __future__ import print_function
"""
    A simple distributed monitoring tool with plugin support
    author: Feiyi Wang <fwang2@ornl.gov>

"""
import sys
import signal
import logging
from logging.handlers import SysLogHandler
import ConfigParser
import argparse
from oddmon.daemon import Daemon

# Globals
logger  = logging.getLogger("app")
ARGS    = None

class G:
    config_file = None
    fmt = None
    console_handler = None
    file_handler = None
    username = None
    password = None
    broker = None
    routing_key = None
    queue = None

def parse_args():
    parser = argparse.ArgumentParser(description="ODDMON program")

    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("-v", "--verbose", default=False, action="store_true",
                               help="verbose output")
    parent_parser.add_argument("-C", "--console", default=False, action="store_true",
                               help="log to the console (instead of syslog)")
    parent_parser.add_argument("--drain", default=False, action="store_true",
                               help="'drain mode' - Just retrieve messages from the queue, but don't actually process them")
    parent_parser.add_argument("--cfgfile", required=True,  help="configure file")
    parent_parser.add_argument("--stop", default=False, action="store_true")
    parent_parser.add_argument("--start", default=False, action="store_true")
    subparsers = parser.add_subparsers(help="Provide one of the sub-commands")
    collect_parser = subparsers.add_parser("collect", parents=[parent_parser], help="Run in collector mode")
    collect_parser.add_argument("--pid", default="collect.pid")
    collect_parser.set_defaults(func=main_collect)
    aggregate_parser = subparsers.add_parser("aggregate", parents=[parent_parser], help="Run in aggregator mode")
    aggregate_parser.add_argument("--pid", default="aggregate.pid")
    aggregate_parser.set_defaults(func=main_aggregate)
    myargs = parser.parse_args()
    return myargs

def sig_handler(signal, frame):
    print("\tUser cancelled ... cleaning up")
    sys.exit(0)

class CollectDaemon(Daemon):
    def run(self):
        from oddmon import oddpub
        oddpub.ARGS = ARGS
        oddpub.main(G.config_file)

class AggregateDaemon(Daemon):
    def run(self):
        from oddmon import oddsub
        oddsub.ARGS = ARGS
        oddsub.main(G.config_file)


def handle(p):
    global logger
    if ARGS.stop:
            p.stop()
    elif ARGS.start:
            logger.removeHandler(G.console_handler)
            p.start()
    else:
            p.run()


def main_aggregate():
    p = AggregateDaemon(ARGS.pid)
    handle(p)

def main_collect():
    p = CollectDaemon(ARGS.pid)
    handle(p)


def setup_logging(loglevel, console):
    global logger

    level = getattr(logging, loglevel.upper())

    fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.setLevel(level)

    if console:
      console_handler = logging.StreamHandler();
      console_handler.setFormatter(fmt)
      logger.addHandler(console_handler)
    else:
      syslog_handler = SysLogHandler('/dev/log', SysLogHandler.LOG_DAEMON)
      syslog_handler.setFormatter(fmt)
      logger.addHandler(syslog_handler)
      
    logger.propagate = False
    
    # Configure the logger settings for pika to match what we've
    # just set up.  (Pika is the AMQP client library)
    pika_logger = logging.getLogger("pika")
    if level == logging.DEBUG:
        level = logging.INFO # pika's DEBUG is really too verbose for us
    pika_logger.setLevel( level)
    for h in logger.handlers:
        pika_logger.addHandler(h)
    
    
    
def main():
    global logger, ARGS

    signal.signal(signal.SIGINT, sig_handler)

    ARGS = parse_args()

    if ARGS.verbose:
        setup_logging("debug", ARGS.console)
    else:
        setup_logging("info", ARGS.console)

    logger.debug(ARGS)

    G.config = ConfigParser.SafeConfigParser()
    try:
        G.config.read(ARGS.cfgfile)
        G.config_file = ARGS.cfgfile
        G.url = G.config.get("DB", "url")
        G.broker = G.config.get("rabbitmq", "broker")
        G.username = G.config.get("rabbitmq", "username")
        G.password = G.config.get("rabbitmq", "password")
        G.routing_key = G.config.get("rabbitmq", "routing_key")
        G.queue = G.config.get("rabbitmq", "queue")
    except Exception, e:
        logger.error("Can't read configuration file")
        logger.error("Reason: %s" % e)
        sys.exit(1)

    ARGS.func()

if __name__ == "__main__": main()

