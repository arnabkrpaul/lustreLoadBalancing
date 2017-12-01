#!/usr/bin/env python

import sys
import logging
import json
import ast
import sql
import plugins
import ConfigParser
import hostlist
import pika
import ssl   # for encrypted connections to the RabbitMQ broker
import os

ARGS    = None
logger  = None

class G:
    subscribers = []
    channel = None
    parameters = None
    connection = None
    queue = None

def save_msg(msg):
    blob = json.loads(msg[0])
    for metric, stats in blob.iteritems():
        stats = ast.literal_eval(str(stats))
        if len(stats) > 0:
            sql.insert_row(metric, stats)
        else:
            logger.debug("[%s] reports empty stats" % metric)
            
def handle_incoming( msg):
    
    if ARGS.drain:
        return # don't actually process the message - just drain it
               # from the queue
    
    #msg is a list (with just one element) of JSON-encoded strings   
    blob = json.loads(msg)
    logger.debug( "blob keys: %s"%blob.keys())
    
    for name, mod in plugins.found():
        uname = unicode(name)
        if blob.has_key( uname):
            logger.debug( "Matched %s - about to call save_stats()"%name)
            mod.save_stats(blob[uname])

    # TODO: ought to check that there were no unhandled items in msg...

def on_connected(connection):
    """Called when we are fully connected to RabbitMQ"""
    # Open a channel
    connection.channel(on_channel_open)

def on_channel_open(new_channel):
    """Called when our channel has opened"""
    global channel
    channel = new_channel
    channel.queue_declare(queue=G.queue, durable=True, exclusive=False, auto_delete=False, callback=on_queue_declared)

def on_queue_declared(frame):
    """Called when RabbitMQ has told us our Queue has been declared, frame is the response from RabbitMQ"""
    channel.basic_consume(handle_delivery, queue=G.queue)

def handle_delivery(channel, method, header, body):
    """Called when we receive a message from RabbitMQ"""
    handle_incoming(body)
    channel.basic_ack(delivery_tag = method.delivery_tag)

def rmq_init(config):
    '''
    Connect to the rabbitmq broker and then loop waiting on received data.
    
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
        
        G.queue = config.get("rabbitmq", "queue")
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
    connection = pika.SelectConnection(parameters, on_connected)

    try:
        connection.ioloop.start()
    except KeyboardInterrupt:
        connection.close()
        connection.ioloop.start()

def main(config_file):
    global logger
    logger = logging.getLogger("app.%s" % __name__)
    
    config = ConfigParser.SafeConfigParser()
    try:
        config.read(config_file)
        url = config.get("DB", "url")
    except Exception, e:
        logger.error("Can't read configuration file")
        logger.error("Reason: %s" % e)
        sys.exit(1)
    try:
        disabled_plugins = config.get( "global", "disabled_plugins").split(',')
        disabled_plugins = map( str.strip, disabled_plugins)
    except ConfigParser.NoOptionError:
        # This is no problem.  The disabled_plugins config is optional
        disabled_plugins = [ ]

    
    sql.db_init(url)

    # find and initialize all plugin modules
    plugins.scan(os.path.dirname(os.path.realpath(__file__))+"/metric_plugins", disabled_plugins)
    plugins.init( config_file, True)
    
    # Print a warning if we're only draining the queue
    if ARGS.drain:
        logger.warning("Running in 'drain mode'! Messages will be extracted from the queue, but not processed.")
    
    rmq_init( config)

    # we kick off the event loop with rmq_init()
    # after that, all we have to do is sit tight
    
    #TODO: Intercept Ctrl-C and run plugins.cleanup( True)

if __name__ == "__main__": main()
