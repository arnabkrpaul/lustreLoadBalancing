#!/usr/bin/env python
__version__ = "0.1"
"""
    A simple distributed monitoring tool with plugin support

"""
import sys
import time
import random
import logging
import json
import plugins
import ConfigParser
import pika  # RabbitMQ client library
import ssl   # for encrypted connections to the RabbitMQ broker
import os

# Globals
logger  = None
ARGS    = None

class G:
    config = None
    channel = None
    connection = None
    routing_key = None


def rmq_init(config):
    '''
    Connect to the rabbitmq broker.
    
    config is a ConfigParser object that has already been set up. (That is,
    config.read() has been successfully called.)
    '''   
    try:
        broker = config.get("rabbitmq", "broker")
        username = config.get("rabbitmq", "username")
        password = config.get("rabbitmq", "password")
        port = config.getint("rabbitmq", "port")
        virt_host = config.get("rabbitmq", "virt_host")
        use_ssl = config.getboolean("rabbitmq", "use_ssl")
        
        G.routing_key = config.get("rabbitmq", "routing_key")
    except Exception, e:
        logger.critical('Failed to parse the "rabbitmq" section of the config file.')
        logger.critical('Reason: %s' % e)
        sys.exit(1)
    
    if use_ssl:
    # ToDo: These ssl settings are specific to rmq1.ccs.ornl.gov
    # I don't know if they're correct for other brokers
        ssl_opts=({"ca_certs"   : "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
                   "cert_reqs"  : ssl.CERT_REQUIRED,
                   "server_side": False})
    else:
        ssl_opts = None
    
    creds = pika.PlainCredentials( username, password)

    parameters = pika.ConnectionParameters(
        host=broker,
        port=port,
        virtual_host=virt_host,
        credentials = creds,
        ssl=use_ssl,
        ssl_options=ssl_opts)
    
    # The RabbitMQ server can't handle a bunch of clients attempting to 
    # simultaneously open connections and this is very likely to happen
    # if one of the admins uses pdsh to start the clients on all the servers.
    # So, we have to be clever about connecting:
    # Connection attempts happen inside a loop. (And the loop will terminate
    # after a fixed amount of time if we haven't successfully connected.)
    # Inside the loop, we'll sleep for a random amount of time in order to
    # spread the load out a bit.
    max_time = time.time() + 120 # spend a max of 2 minutes attempting to connect
    while (G.connection is None and time.time() < max_time):
        try:
            # Wait a small amount of time before attempting to connect
            wait_time = random.random() * 1.0
            time.sleep(wait_time)
            G.connection = pika.BlockingConnection(parameters)
            is_connected = True
        except pika.exceptions.AMQPConnectionError, e:
            # if we get a timeout error, wait a little bit longer before
            # trying again
            if "timed out" in str(e):
                wait_time = 1.0 + (random.random() * 4.0)
                logger.warning( "Timeout error connecting to RMQ server.  " \
                                "Retrying in %fs."%wait_time)
                time.sleep(wait_time)
            else:
                # Re-throw the exception
                raise
    # Exited from the while loop.  Did we connect?
    if G.connection is None:
        logger.critical( "Failed to connect to the RMQ server.")
        raise RuntimeError( "Failed to connect to the RMQ server.")
        
    G.channel = G.connection.channel()


def sig_handler(signal, frame):
    print "\tUser cancelled ... cleaning up"
    plugins.cleanup()
    sys.exit(0)


def main( config_file):
    global logger, ARGS
    logger = logging.getLogger("app.%s" % __name__)

    config = ConfigParser.SafeConfigParser()
    try:
        config.read(config_file)
    except Exception, e:
        logger.critical("Can't read configuration file")
        logger.critical("Reason: %s" % e)
        sys.exit(1)

    try:
        sleep_interval = config.getint("global", "interval")
    except Exception, e:
        logger.critical('Failed to parse the "global" section of the ' \
                        'config file.')
        logger.critical('Reason: %s' % e)
        sys.exit(1)
    try:
        disabled_plugins = config.get( "global", "disabled_plugins").split(',')
        disabled_plugins = map( str.strip, disabled_plugins)
    except ConfigParser.NoOptionError:
        # This is no problem.  The disabled_plugins config is optional
        disabled_plugins = [ ]



    # This will throw an exception if it fails to connect
    rmq_init(config)

    # initialize all metric modules
    plugins.scan(os.path.dirname(os.path.realpath(__file__))+"/metric_plugins", disabled_plugins)
    plugins.init( config_file, False)

    while True:
        merged = {}
        for name, mod in plugins.found():
            msg = None
            try:
                msg = mod.get_stats()
            except Exception as e:
                logger.exception("%s --->%s\n" % (name, e))

            if msg: merged[name] = msg

        if len(merged) > 0:
            logger.debug("publish: %s" % merged)
            G.channel.basic_publish(exchange='', routing_key=G.routing_key,
                                    body=(json.dumps(merged)))
        else:
            logger.warn("Empty stats")

        time.sleep(sleep_interval)


    plugins.cleanup( False)

if __name__ == "__main__": main()

